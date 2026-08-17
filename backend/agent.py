from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

from backend.config import (
    OPENAI_API_KEY,
    AGENT_MODEL,
)

from backend.conversation_service import (
    get_or_create_conversation,
    get_messages,
    save_message,
    save_workflow_state,
    get_workflow_state,
    clear_workflow_state,
)

from backend.intent import (
    classify_intent,
)

from backend.action_classifier import (
    classify_action,
)

from backend.workflows.scheduling_service import (
    run_scheduling_workflow,
)

from backend.workflows.booking_graph import (
    parse_request,
)

from prompts.build_prompt import (
    build_system_prompt,
)

from backend.rag.policy_rag import (
    answer_policy_question,
)


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

def get_system_prompt():

    colombo_tz = ZoneInfo(
        "Asia/Colombo"
    )

    today = datetime.now(
        colombo_tz
    ).strftime(
        "%Y-%m-%d"
    )

    return build_system_prompt(
        today
    )


# ============================================================
# FORMAT AVAILABILITY SLOTS
# ============================================================

def format_availability_slots(
    slots: list,
):

    if not slots:

        return (
            "No available appointment "
            "slots were found."
        )

    lines = [
        "Here are the available appointment slots:"
    ]

    for slot in slots:

        try:

            start = datetime.fromisoformat(
                slot["start"]
            )

            end = datetime.fromisoformat(
                slot["end"]
            )

            start_text = start.strftime(
                "%I:%M %p"
            ).lstrip("0")

            end_text = end.strftime(
                "%I:%M %p"
            ).lstrip("0")

            lines.append(
                f"- {start_text} to {end_text}"
            )

        except (
            KeyError,
            ValueError,
            TypeError,
        ):

            continue

    if len(lines) == 1:

        return (
            "No available appointment "
            "slots were found."
        )

    lines.append(
        "Please let me know which one "
        "you would like to book."
    )

    return "\n".join(
        lines
    )


# ============================================================
# SLOT SELECTION MESSAGE DETECTION
# ============================================================

def is_slot_selection_message(
    user_input: str,
) -> bool:

    text = user_input.strip().lower()

    if not text:
        return False

    # Examples:
    #
    # 7 PM
    # 7:30 PM
    # 19:30
    # 7pm
    # 7:30pm

    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
    ]

    normalized = text.upper()

    for fmt in formats:

        try:

            datetime.strptime(
                normalized,
                fmt,
            )

            return True

        except ValueError:

            pass

    return False


# ============================================================
# SELECT SLOT FROM USER MESSAGE
# ============================================================

def select_slot_from_message(
    user_input: str,
    available_slots: list,
):
    """
    Match a user's requested time against the
    previously returned available slots.

    Examples:

        7 PM
        7:30 PM
        19:30
    """

    text = user_input.strip()

    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
    ]

    requested_time = None

    for fmt in formats:

        try:

            requested_time = datetime.strptime(
                text.upper(),
                fmt,
            ).time()

            break

        except ValueError:

            continue

    if not requested_time:

        return None

    for slot in available_slots:

        try:

            start = datetime.fromisoformat(
                slot["start"]
            )

            if (
                start.hour
                == requested_time.hour
                and
                start.minute
                == requested_time.minute
            ):

                return slot

        except (
            KeyError,
            ValueError,
            TypeError,
        ):

            continue

    return None


# ============================================================
# SAVE BOOKING CONTEXT
# ============================================================

def save_booking_context(
    db,
    conversation_id,
    user_id,
    user_input,
    conversation_history,
):

    """
    Save the important information from a booking
    request so follow-up messages can continue it.

    Example:

        Book tomorrow at 7 PM
        email
        7 PM unavailable
        how about 8 PM
    """

    try:

        state = {
            "user_id": user_id,
            "user_input": user_input,
            "conversation_history":
                conversation_history,
        }

        parsed = parse_request(
            state
        )

        booking_state = {
            "action": "BOOK",

            "awaiting_booking_followup":
                True,

            "email":
                parsed.get(
                    "email"
                ),

            "title":
                parsed.get(
                    "title",
                    "Appointment",
                ),

            "duration_minutes":
                parsed.get(
                    "duration_minutes",
                    30,
                ),

            "window_start":
                parsed.get(
                    "window_start"
                ),

            "window_end":
                parsed.get(
                    "window_end"
                ),

            "exact_start":
                parsed.get(
                    "exact_start"
                ),

            "exact_end":
                parsed.get(
                    "exact_end"
                ),

            "needs_slot_search":
                parsed.get(
                    "needs_slot_search",
                    False,
                ),

            "auto_book":
                parsed.get(
                    "auto_book",
                    True,
                ),
        }

        save_workflow_state(
            db,
            conversation_id,
            booking_state,
        )

        print(
            "\n=== SAVED BOOKING CONTEXT ==="
        )

        print(
            booking_state
        )

        print(
            "=============================\n"
        )

        return booking_state

    except Exception as e:

        print(
            "\n=== BOOKING CONTEXT ERROR ==="
        )

        print(
            str(e)
        )

        print(
            "==============================\n"
        )

        return None


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def run_agent(
    db,
    user_id,
    user_input,
):

    # ========================================================
    # GET CONVERSATION
    # ========================================================

    conversation = get_or_create_conversation(
        db,
        user_id,
    )

    messages = get_messages(
        db,
        conversation.id,
    )

    # ========================================================
    # GET WORKFLOW STATE
    # ========================================================

    workflow_state = get_workflow_state(
        db,
        conversation.id,
    )

    print(
        "\n=== WORKFLOW STATE ==="
    )

    print(
        workflow_state
    )

    print(
        "======================\n"
    )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

    save_message(
        db,
        conversation.id,
        "user",
        user_input,
    )

    # ========================================================
    # PENDING CANCELLATION CONFIRMATION
    # ========================================================

    if (
        workflow_state
        and workflow_state.get(
            "awaiting_cancellation_confirmation"
        )
    ):

        text = user_input.strip().lower()

        yes_values = {
            "yes",
            "y",
            "yes please",
            "confirm",
            "confirmed",
            "do it",
            "go ahead",
            "cancel it",
        }

        no_values = {
            "no",
            "n",
            "no thanks",
            "don't",
            "dont",
            "keep it",
            "keep the appointment",
        }

        # ----------------------------------------------------
        # CONFIRM
        # ----------------------------------------------------

        if text in yes_values:

            event_id = workflow_state.get(
                "event_id"
            )

            if not event_id:

                clear_workflow_state(
                    db,
                    conversation.id,
                )

                response = (
                    "I couldn't find the appointment "
                    "to cancel."
                )

                save_message(
                    db,
                    conversation.id,
                    "assistant",
                    response,
                )

                return response

            from backend.calendar_service import (
                delete_event,
            )

            result = delete_event(
                user_id=user_id,
                event_id=event_id,
            )

            print(
                "DELETE RESULT:",
                result,
            )

            if result.get("success"):

                response = (
                    "Your appointment has been "
                    "cancelled successfully."
                )

            else:

                response = result.get(
                    "error",
                    "Unable to cancel the appointment.",
                )

            clear_workflow_state(
                db,
                conversation.id,
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # REJECT
        # ----------------------------------------------------

        if text in no_values:

            clear_workflow_state(
                db,
                conversation.id,
            )

            response = (
                "Okay, I won't cancel the appointment."
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # NEW REQUEST
        # ----------------------------------------------------

        clear_workflow_state(
            db,
            conversation.id,
        )

        workflow_state = None

    # ========================================================
    # PENDING RESCHEDULING CONFIRMATION
    # ========================================================

    if (
        workflow_state
        and workflow_state.get(
            "awaiting_rescheduling_confirmation"
        )
    ):

        text = user_input.strip().lower()

        yes_values = {
            "yes",
            "y",
            "yes please",
            "confirm",
            "confirmed",
            "do it",
            "go ahead",
            "reschedule it",
        }

        no_values = {
            "no",
            "n",
            "no thanks",
            "don't",
            "dont",
            "keep it",
            "keep the appointment",
        }

        # ----------------------------------------------------
        # CONFIRM
        # ----------------------------------------------------

        if text in yes_values:

            event_id = workflow_state.get(
                "event_id"
            )

            new_start = workflow_state.get(
                "new_start"
            )

            new_end = workflow_state.get(
                "new_end"
            )

            if (
                not event_id
                or not new_start
                or not new_end
            ):

                clear_workflow_state(
                    db,
                    conversation.id,
                )

                response = (
                    "I couldn't complete the "
                    "rescheduling request."
                )

                save_message(
                    db,
                    conversation.id,
                    "assistant",
                    response,
                )

                return response

            from backend.calendar_service import (
                update_event,
            )

            result = update_event(
                user_id=user_id,
                event_id=event_id,
                start=new_start,
                end=new_end,
            )

            print(
                "RESCHEDULE RESULT:",
                result,
            )

            if result.get("success"):

                response = (
                    "Your appointment has been "
                    "rescheduled successfully."
                )

                link = result.get(
                    "link"
                )

                if link:

                    response += (
                        f" You can view the appointment "
                        f"here: {link}"
                    )

            else:

                response = result.get(
                    "error",
                    "Unable to reschedule the appointment.",
                )

            clear_workflow_state(
                db,
                conversation.id,
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # REJECT
        # ----------------------------------------------------

        if text in no_values:

            clear_workflow_state(
                db,
                conversation.id,
            )

            response = (
                "Okay, I won't reschedule the appointment."
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # NEW REQUEST
        # ----------------------------------------------------

        clear_workflow_state(
            db,
            conversation.id,
        )

        workflow_state = None

    # ========================================================
    # PENDING SLOT SELECTION
    #
    # IMPORTANT:
    #
    # Only enter this block when the user's message
    # actually looks like a time.
    #
    # This prevents a fresh request such as:
    #
    # "Show me available slots around 7 PM tomorrow"
    #
    # from being treated as a slot selection.
    # ========================================================

    if (
        workflow_state
        and workflow_state.get(
            "awaiting_slot_selection"
        )
        and is_slot_selection_message(
            user_input
        )
    ):

        print(
            "\n=== PENDING SLOT SELECTION ==="
        )

        print(
            "USER RESPONSE:",
            user_input,
        )

        print(
            "AVAILABLE SLOTS:",
            workflow_state.get(
                "available_slots",
                [],
            ),
        )

        print(
            "===============================\n"
        )

        selected_slot = select_slot_from_message(
            user_input,
            workflow_state.get(
                "available_slots",
                [],
            ),
        )

        if not selected_slot:

            response = (
                "I couldn't identify that appointment "
                "slot. Please choose one of the "
                "available times."
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # Save selected slot
        # ----------------------------------------------------

        workflow_state[
            "selected_slot"
        ] = selected_slot

        workflow_state[
            "awaiting_slot_selection"
        ] = False

        # ----------------------------------------------------
        # Email already available
        # ----------------------------------------------------

        if workflow_state.get(
            "email"
        ):

            workflow_state[
                "awaiting_email"
            ] = False

            save_workflow_state(
                db,
                conversation.id,
                workflow_state,
            )

            # Complete booking
            result = run_scheduling_workflow(
                user_id=user_id,
                user_input=user_input,
                action="SELECT_SLOT",
                conversation_history=messages,
            )

            response = result.get(
                "message",
                "The slot has been selected.",
            )

            link = result.get(
                "link"
            )

            if link:

                response += (
                    f" You can view the appointment "
                    f"here: {link}"
                )

            clear_workflow_state(
                db,
                conversation.id,
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # Ask for email
        # ----------------------------------------------------

        workflow_state[
            "awaiting_email"
        ] = True

        save_workflow_state(
            db,
            conversation.id,
            workflow_state,
        )

        response = (
            "What email address should I "
            "associate with the appointment?"
        )

        save_message(
            db,
            conversation.id,
            "assistant",
            response,
        )

        return response

    # ========================================================
    # PENDING EMAIL
    # ========================================================

    if (
        workflow_state
        and workflow_state.get(
            "awaiting_email"
        )
    ):

        email = user_input.strip()

        # ----------------------------------------------------
        # Validate email
        # ----------------------------------------------------

        if (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):

            response = (
                "Please provide a valid email "
                "address."
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # Save email
        # ----------------------------------------------------

        workflow_state[
            "email"
        ] = email

        workflow_state[
            "awaiting_email"
        ] = False

        # ====================================================
        # SELECTED SLOT EXISTS
        # ====================================================

        if workflow_state.get(
            "selected_slot"
        ):

            save_workflow_state(
                db,
                conversation.id,
                workflow_state,
            )

            result = run_scheduling_workflow(
                user_id=user_id,
                user_input=user_input,
                action="BOOK",
                conversation_history=messages,
            )

            response = result.get(
                "message",
                "Unable to complete the booking.",
            )

            link = result.get(
                "link"
            )

            if link:

                response += (
                    f" You can view the appointment "
                    f"here: {link}"
                )

            clear_workflow_state(
                db,
                conversation.id,
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ====================================================
        # NO SELECTED SLOT
        #
        # Keep booking state so:
        #
        # "how about 8 PM"
        #
        # can continue the request.
        # ====================================================

        workflow_state[
            "awaiting_booking_followup"
        ] = True

        save_workflow_state(
            db,
            conversation.id,
            workflow_state,
        )

        result = run_scheduling_workflow(
            user_id=user_id,
            user_input=user_input,
            action="BOOK",
            conversation_history=messages,
        )

        print(
            "\n=== BOOKING AFTER EMAIL ==="
        )

        print(
            result
        )

        print(
            "===========================\n"
        )

        if result.get(
            "success"
        ):

            response = result.get(
                "message",
                "Your appointment has been "
                "successfully booked.",
            )

            link = result.get(
                "link"
            )

            if link:

                response += (
                    f" You can view the appointment "
                    f"here: {link}"
                )

            clear_workflow_state(
                db,
                conversation.id,
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        response = result.get(
            "message",
            "The requested time is not available.",
        )

        save_workflow_state(
            db,
            conversation.id,
            workflow_state,
        )

        save_message(
            db,
            conversation.id,
            "assistant",
            response,
        )

        return response

    # ========================================================
    # PENDING BOOKING FOLLOW-UP
    #
    # Handles:
    #
    # Book tomorrow at 7 PM
    # 7 PM unavailable
    # how about 8 PM
    # ========================================================

    if (
        workflow_state
        and workflow_state.get(
            "awaiting_booking_followup"
        )
    ):

        text = user_input.strip().lower()

        follow_up_phrases = (
            "how about",
            "what about",
            "make it",
            "change it to",
            "try",
            "instead",
            "move it to",
        )

        is_time_followup = any(
            phrase in text
            for phrase in follow_up_phrases
        )

        if is_time_followup:

            print(
                "\n=== BOOKING TIME FOLLOW-UP ==="
            )

            print(
                "PREVIOUS STATE:",
                workflow_state,
            )

            print(
                "CURRENT MESSAGE:",
                user_input,
            )

            print(
                "================================\n"
            )

            result = run_scheduling_workflow(
                user_id=user_id,
                user_input=user_input,
                action="BOOK",
                conversation_history=messages,
            )

            print(
                "\n=== FOLLOW-UP BOOKING RESULT ==="
            )

            print(
                result
            )

            print(
                "=================================\n"
            )

            if result.get(
                "needs_input"
            ):

                save_workflow_state(
                    db,
                    conversation.id,
                    {
                        **workflow_state,
                        "awaiting_booking_followup":
                            True,
                    },
                )

                response = result.get(
                    "message",
                    "What email address should I "
                    "associate with the appointment?",
                )

                save_message(
                    db,
                    conversation.id,
                    "assistant",
                    response,
                )

                return response

            response = result.get(
                "message",
                "Unable to process the "
                "appointment request.",
            )

            link = result.get(
                "link"
            )

            if link:

                response += (
                    f" You can view the appointment "
                    f"here: {link}"
                )

            if result.get(
                "success"
            ):

                clear_workflow_state(
                    db,
                    conversation.id,
                )

            else:

                save_workflow_state(
                    db,
                    conversation.id,
                    workflow_state,
                )

            save_message(
                db,
                conversation.id,
                "assistant",
                response,
            )

            return response

        # ----------------------------------------------------
        # Not a time follow-up → new request
        # ----------------------------------------------------

        clear_workflow_state(
            db,
            conversation.id,
        )

        workflow_state = None

    # ========================================================
    # CLASSIFY INTENT
    # ========================================================

    intent = classify_intent(
        user_input,
        conversation_history=messages,
    )

    print(
        "\n=== INTENT ==="
    )

    print(
        intent
    )

    print(
        "===============\n"
    )

    # ========================================================
    # SCHEDULING
    # ========================================================

    if intent == "SCHEDULING":

        action = classify_action(
            user_input,
            conversation_history=messages,
        )

        print(
            "\n=== ACTION ==="
        )

        print(
            action
        )

        print(
            "===============\n"
        )

        # ----------------------------------------------------
        # BOOKING
        # ----------------------------------------------------

        if action == "BOOK":

            save_booking_context(
                db=db,
                conversation_id=conversation.id,
                user_id=user_id,
                user_input=user_input,
                conversation_history=messages,
            )

            workflow_state = (
                get_workflow_state(
                    db,
                    conversation.id,
                )
            )

        # ----------------------------------------------------
        # RUN WORKFLOW
        # ----------------------------------------------------

        result = run_scheduling_workflow(
            user_id=user_id,
            user_input=user_input,
            action=action,
            conversation_history=messages,
        )

        print(
            "\n=== SCHEDULING RESULT ==="
        )

        print(
            result
        )

        print(
            "==========================\n"
        )

        # ====================================================
        # BOOKING NEEDS INPUT
        # ====================================================

        if (
            action == "BOOK"
            and result.get(
                "needs_input"
            )
        ):

            current_state = (
                get_workflow_state(
                    db,
                    conversation.id,
                )
                or {}
            )

            current_state[
                "action"
            ] = "BOOK"

            current_state[
                "awaiting_booking_followup"
            ] = True

            current_state.setdefault(
                "email",
                None,
            )

            save_workflow_state(
                db,
                conversation.id,
                current_state,
            )

            final_response = result.get(
                "message",
                "What email address should I "
                "associate with the appointment?",
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                final_response,
            )

            return final_response

        # ====================================================
        # CANCELLATION CONFIRMATION
        # ====================================================

        if (
            action == "CANCEL"
            and result.get(
                "needs_confirmation"
            )
        ):

            save_workflow_state(
                db,
                conversation.id,
                {
                    "action": "CANCEL",

                    "awaiting_cancellation_confirmation":
                        True,

                    "event_id":
                        result.get(
                            "event_id"
                        ),

                    "event":
                        result.get(
                            "event",
                            {}
                        ),
                },
            )

            final_response = result.get(
                "message",
                "Would you like me to cancel it?",
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                final_response,
            )

            return final_response

        # ====================================================
        # RESCHEDULING CONFIRMATION
        # ====================================================

        if (
            action == "RESCHEDULE"
            and result.get(
                "needs_confirmation"
            )
        ):

            save_workflow_state(
                db,
                conversation.id,
                {
                    "action": "RESCHEDULE",

                    "awaiting_rescheduling_confirmation":
                        True,

                    "event_id":
                        result.get(
                            "event_id"
                        ),

                    "event":
                        result.get(
                            "event",
                            {}
                        ),

                    "old_start":
                        result.get(
                            "old_start"
                        ),

                    "old_end":
                        result.get(
                            "old_end"
                        ),

                    "new_start":
                        result.get(
                            "new_start"
                        ),

                    "new_end":
                        result.get(
                            "new_end"
                        ),
                },
            )

            final_response = result.get(
                "message",
                "Would you like me to reschedule it?",
            )

            save_message(
                db,
                conversation.id,
                "assistant",
                final_response,
            )

            return final_response

        # ====================================================
        # AVAILABILITY
        # ====================================================

        if action == "CHECK_AVAILABILITY":

            slots = result.get(
                "slots",
                []
            )

            # Keep the human-readable response for conversation history,
            # but return the structured availability data to the frontend.
            formatted_response = (
                format_availability_slots(
                    slots
                )
            )

            final_response = {
                "success": bool(slots),

                "message": (
                    "Here are the available appointment slots:"
                    if slots
                    else "No available appointment slots were found."
                ),

                "slots": slots,

                "window_start": result.get(
                    "window_start"
                ),

                "window_end": result.get(
                    "window_end"
                ),

                "duration_minutes": result.get(
                    "duration_minutes",
                    30,
                ),

                "title": result.get(
                    "title",
                    "Appointment",
                ),
            }

            if slots:

                save_workflow_state(
                    db,
                    conversation.id,
                    {
                        "action":
                            "CHECK_AVAILABILITY",

                        "available_slots":
                            slots,

                        "duration_minutes":
                            result.get(
                                "duration_minutes",
                                30,
                            ),

                        "window_start":
                            result.get(
                                "window_start"
                            ),

                        "window_end":
                            result.get(
                                "window_end"
                            ),

                        "email":
                            result.get(
                                "email"
                            ),

                        "title":
                            result.get(
                                "title",
                                "Appointment",
                            ),

                        "awaiting_slot_selection":
                            True,

                        "awaiting_email":
                            False,

                        "selected_slot":
                            None,
                    },
                )

            else:

                clear_workflow_state(
                    db,
                    conversation.id,
                )

            save_message(
                db,
                conversation.id,
                "assistant",
                formatted_response,
            )

            return final_response

        # ====================================================
        # NORMAL SCHEDULING RESPONSE
        # ====================================================

        final_response = result.get(
            "message",
            "Unable to process the appointment request.",
        )

        link = result.get(
            "link"
        )

        if link:

            final_response += (
                f" You can view the appointment "
                f"here: {link}"
            )

        if (
            action == "BOOK"
            and result.get(
                "success"
            )
        ):

            clear_workflow_state(
                db,
                conversation.id,
            )

        save_message(
            db,
            conversation.id,
            "assistant",
            final_response,
        )

        return final_response

    # ========================================================
    # POLICY / RAG REQUEST
    # ========================================================

    policy_keywords = (
        "policy",
        "policies",
        "cancellation policy",
        "cancellation",
        "rescheduling policy",
        "rescheduling",
        "refund",
        "booking rules",
        "appointment rules",
        "how late",
        "how early",
        "default duration",
        "appointment duration",
        "email required",
        "privacy",
        "working hours",
        "appointment hours",
    )

    is_policy_question = any(
        keyword in user_input.lower()
        for keyword in policy_keywords
    )

    if is_policy_question:

        final_response = answer_policy_question(
            user_input
        )

        if final_response:

            save_message(
                db,
                conversation.id,
                "assistant",
                final_response,
            )

            return final_response

    # ========================================================
    # NORMAL LLM REQUEST
    # ========================================================

    llm_messages = [
        {
            "role": "system",
            "content": get_system_prompt(),
        }
    ]

    llm_messages.extend(
        messages
    )

    llm_messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    response = client.chat.completions.create(
        model=AGENT_MODEL,
        messages=llm_messages,
    )

    final_response = (
        response
        .choices[0]
        .message
        .content
    )

    save_message(
        db,
        conversation.id,
        "assistant",
        final_response,
    )

    return final_response