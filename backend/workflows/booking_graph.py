from typing import TypedDict
import json
import logging
import time

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openai import OpenAI, RateLimitError
from langgraph.graph import StateGraph, START, END

from backend.config import (
    OPENAI_API_KEY,
    AGENT_MODEL,
)
from backend.logging_utils import log_debug

from backend.calendar_service import (
    find_available_slots,
    check_availability,
    create_event,
)


logger = logging.getLogger(__name__)


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# ============================================================
# STATE
# ============================================================

class BookingState(TypedDict, total=False):

    user_id: int
    user_input: str

    conversation_history: list

    title: str
    email: str

    window_start: str
    window_end: str

    exact_start: str
    exact_end: str

    duration_minutes: int

    needs_slot_search: bool
    auto_book: bool

    missing_fields: list

    available_slots: list
    selected_slot: dict

    booking_result: dict

    final_response: dict


# ============================================================
# HELPERS
# ============================================================

def _replace_date_in_iso(
    value: str,
    target_date,
):
    """
    Replace or add the calendar date portion.

    Supports:

        2026-08-17T19:00:00+05:30
        19:00:00+05:30
        19:00:00
        19:00
    """

    if not value:
        return value

    try:

        # ====================================================
        # FULL DATETIME
        # ====================================================

        if "T" in value:

            dt = datetime.fromisoformat(
                value
            )

            dt = dt.replace(
                year=target_date.year,
                month=target_date.month,
                day=target_date.day,
            )

            return dt.isoformat()

        # ====================================================
        # TIME WITH TIMEZONE
        # ====================================================

        try:

            parsed_time = datetime.strptime(
                value,
                "%H:%M:%S%z",
            ).time()

        except ValueError:

            # =================================================
            # TIME WITHOUT TIMEZONE
            # =================================================

            try:

                parsed_time = datetime.strptime(
                    value,
                    "%H:%M:%S",
                ).time()

            except ValueError:

                parsed_time = datetime.strptime(
                    value,
                    "%H:%M",
                ).time()

        dt = datetime.combine(
            target_date,
            parsed_time,
        )

        dt = dt.replace(
            tzinfo=ZoneInfo(
                "Asia/Colombo"
            )
        )

        return dt.isoformat()

    except (
        ValueError,
        TypeError,
    ) as e:

        log_debug(logger,
            "DATE NORMALIZATION ERROR:",
            value,
            e,
        )

        return value
def _contains_relative_word(
    text: str,
    word: str,
):
    return word.lower() in text.lower()


def _normalize_relative_dates(
    data: dict,
    user_input: str,
):
    """
    Deterministically correct relative dates such as
    'today' and 'tomorrow'.

    The LLM extracts the time, but we don't allow it to
    hallucinate the calendar date.
    """

    colombo_tz = ZoneInfo(
        "Asia/Colombo"
    )

    today = datetime.now(
        colombo_tz
    ).date()

    user_text = user_input.lower()

    user_text = user_text.replace(
        "tmorrow",
        "tomorrow",
    )

    user_text = user_text.replace(
        "tommorow",
        "tomorrow",
    )

    user_text = user_text.replace(
        "tomorow",
        "tomorrow",
    )

    # --------------------------------------------------------
    # TOMORROW
    # --------------------------------------------------------

    if _contains_relative_word(
        user_text,
        "tomorrow",
    ):

        target_date = (
            today
            + timedelta(
                days=1
            )
        )

        for key in [
            "window_start",
            "window_end",
            "exact_start",
            "exact_end",
        ]:

            if data.get(key):

                data[key] = _replace_date_in_iso(
                    data[key],
                    target_date,
                )

    # --------------------------------------------------------
    # TODAY
    # --------------------------------------------------------

    elif _contains_relative_word(
        user_text,
        "today",
    ):

        target_date = today

        for key in [
            "window_start",
            "window_end",
            "exact_start",
            "exact_end",
        ]:

            if data.get(key):

                data[key] = _replace_date_in_iso(
                    data[key],
                    target_date,
                )

    return data


def _calculate_exact_end(
    data: dict,
):
    """
    Calculate exact_end deterministically from exact_start
    and duration_minutes.

    The LLM should extract the requested start time only.
    Python is responsible for calculating the end time so
    appointments crossing midnight are handled correctly.
    """

    exact_start = data.get("exact_start")

    if not exact_start:
        return data

    try:
        start_dt = datetime.fromisoformat(
            exact_start
        )

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(
                tzinfo=ZoneInfo("Asia/Colombo")
            )

        duration_minutes = int(
            data.get(
                "duration_minutes",
                30,
            )
        )

        end_dt = start_dt + timedelta(
            minutes=duration_minutes
        )

        data["exact_start"] = start_dt.isoformat()
        data["exact_end"] = end_dt.isoformat()

        log_debug(logger,
            "\n=== EXACT TIME NORMALIZATION ==="
        )

        log_debug(logger,
            "Exact start:",
            data["exact_start"]
        )

        log_debug(logger,
            "Exact end:",
            data["exact_end"]
        )

        log_debug(logger,
            "Duration:",
            duration_minutes
        )

        log_debug(logger,
            "=================================\n"
        )

    except (
        ValueError,
        TypeError,
    ) as e:

        log_debug(logger,
            "EXACT TIME NORMALIZATION ERROR:",
            e,
        )

    return data


def _extract_previous_booking_context(
    conversation_history: list,
):
    """
    Look through recent conversation history and return
    useful context.

    This is primarily used to help with messages such as:

        how about 8 PM
        what about 9 PM
        make it 10 PM
    """

    context = {
        "last_user_message": None,
        "last_assistant_message": None,
    }

    for message in reversed(
        conversation_history
    ):

        role = message.get(
            "role",
            ""
        )

        content = message.get(
            "content"
        )

        if not content:
            continue

        if (
            role == "user"
            and context["last_user_message"] is None
        ):

            context["last_user_message"] = content

        if (
            role == "assistant"
            and context["last_assistant_message"] is None
        ):

            context["last_assistant_message"] = content

        if (
            context["last_user_message"]
            and context["last_assistant_message"]
        ):

            break

    return context


# ============================================================
# AVAILABILITY FOLLOW-UP HELPERS
# ============================================================

def _is_availability_request(
    text: str,
) -> bool:
    """
    Determine whether a previous request was an
    availability-only request.

    Examples:

        Show me available slots around 7 PM tomorrow
        What times are available tomorrow?
        Show me slots around 3 PM
    """

    text = (
        text
        or ""
    ).lower()

    availability_words = (
        "available",
        "availability",
        "available slots",
        "time slots",
        "slots",
        "free",
        "what times",
        "show me",
        "find me a slot",
    )

    booking_words = (
        "book",
        "schedule",
        "make an appointment",
        "create an appointment",
    )

    has_availability_word = any(
        word in text
        for word in availability_words
    )

    has_booking_word = any(
        word in text
        for word in booking_words
    )

    # Explicit booking language wins.
    if has_booking_word:
        return False

    return has_availability_word


def _inherit_previous_relative_date(
    data: dict,
    previous_user_message: str,
):
    """
    Reuse the date from the previous request when the
    current request is a time-only follow-up.

    Example:

        Previous:
            Show me slots around 3 PM tomorrow

        Current:
            How about 7 PM?

    The current request should still use tomorrow.
    """

    previous_text = (
        previous_user_message
        or ""
    ).lower()

    colombo_tz = ZoneInfo(
        "Asia/Colombo"
    )

    today = datetime.now(
        colombo_tz
    ).date()

    target_date = None

    if "tomorrow" in previous_text:

        target_date = (
            today
            + timedelta(
                days=1
            )
        )

    elif "today" in previous_text:

        target_date = today

    if not target_date:

        return data

    for key in [
        "window_start",
        "window_end",
        "exact_start",
        "exact_end",
    ]:

        if data.get(key):

            data[key] = _replace_date_in_iso(
                data[key],
                target_date,
            )

    return data


def _convert_exact_time_to_availability_window(
    data: dict,
):
    """
    Convert an exact time into a two-hour availability window.

    Example:
        7 PM
        -> 6 PM to 8 PM

    Example:
        11:30 PM
        -> 10:30 PM today to 12:30 AM tomorrow
    """

    exact_start = data.get("exact_start")

    if not exact_start:
        return data

    try:
        start = datetime.fromisoformat(exact_start)

        # Make sure the datetime has Colombo timezone
        if start.tzinfo is None:
            start = start.replace(
                tzinfo=ZoneInfo("Asia/Colombo")
            )

        window_start = start - timedelta(hours=1)
        window_end = start + timedelta(hours=1)

        # Important: this automatically handles midnight rollover.
        data["window_start"] = window_start.isoformat()
        data["window_end"] = window_end.isoformat()

        data["exact_start"] = None
        data["exact_end"] = None

        data["needs_slot_search"] = True
        data["auto_book"] = False

        log_debug(logger, "\n=== CONVERTED AVAILABILITY WINDOW ===")
        log_debug(logger, "Exact:", start.isoformat())
        log_debug(logger, "Window start:", data["window_start"])
        log_debug(logger, "Window end:", data["window_end"])
        log_debug(logger, "====================================\n")

    except (ValueError, TypeError) as e:
        log_debug(logger,
            "AVAILABILITY WINDOW CONVERSION ERROR:",
            exact_start,
            e,
        )

    return data


# ============================================================
# PARSE REQUEST
# ============================================================

def parse_request(
    state: BookingState
):

    conversation_history = state.get(
        "conversation_history",
        []
    )

    colombo_tz = ZoneInfo(
        "Asia/Colombo"
    )

    now = datetime.now(
        colombo_tz
    )

    today = now.strftime(
        "%Y-%m-%d"
    )

    tomorrow = (
        now.date()
        + timedelta(
            days=1
        )
    ).strftime(
        "%Y-%m-%d"
    )

    history = state.get(
        "conversation_history",
        []
    )

    # Keep only recent conversation turns in the LLM prompt.
    #
    # The booking workflow already persists the important
    # booking context separately. Sending the entire historical
    # conversation to gpt-4o can cause unnecessarily large
    # requests and TPM rate-limit failures.
    recent_history = history[-4:]

    history_lines = []

    for message in recent_history:

        role = message.get(
            "role",
            ""
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        history_lines.append(
            f"{role}: {content}"
        )

    history_text = "\n".join(
        history_lines
    )

    history_without_current = list(history)

    if history_without_current:

        last_message = history_without_current[-1]

        if (
            last_message.get("role") == "user"
            and (
                last_message.get("content") or ""
            ).strip()
            == state["user_input"].strip()
        ):
            history_without_current.pop()

    previous_context = (
        _extract_previous_booking_context(
            history_without_current
        )
    )

    previous_user_message = (
        previous_context.get(
            "last_user_message"
        )
        or ""
    )

    previous_assistant_message = (
        previous_context.get(
            "last_assistant_message"
        )
        or ""
    )

    prompt = f"""
Today is {today}.
Tomorrow is {tomorrow}.
Current timezone: Asia/Colombo (+05:30).

IMPORTANT DATE RULE:

Today is EXACTLY:

{today}

Tomorrow is EXACTLY:

{tomorrow}

Never calculate "tomorrow" yourself using another date.

If the user says "tomorrow", every generated timestamp
for that request MUST use:

{tomorrow}

If the user says "today", every generated timestamp
MUST use:

{today}

==================================================
ROLE
==================================================

You are an appointment booking information extractor.

Your job is to extract the information required to
complete an appointment booking OR availability request.

The current request may continue a previous conversation.

==================================================
PREVIOUS CONVERSATION
==================================================

{history_text}

==================================================
RECENT CONTEXT
==================================================

Previous user message:

{previous_user_message}

Previous assistant message:

{previous_assistant_message}

==================================================
CURRENT REQUEST
==================================================

{state["user_input"]}

==================================================
FOLLOW-UP RULE
==================================================

The current request may be a continuation of an existing
booking OR availability conversation.

Short messages can modify the previous request.

BOOKING FOLLOW-UP example:

Previous user:

"Book an appointment tomorrow at 7 PM for 30 minutes"

Assistant:

"The requested time is not available."

Current user:

"How about 8 PM?"

This means:

"Book the same appointment tomorrow at 8 PM for 30 minutes."

Therefore:

- Reuse the previous date.
- Reuse the previous duration.
- Reuse the previous email if it belongs to the
  pending booking.
- Change ONLY the requested time.
- Keep auto_book = true.

Another booking example:

Previous:

"Book an appointment tomorrow at 7 PM"

Assistant:

"What email address should I associate with the appointment?"

Current:

"info@weaveapps.com"

Then:

- Reuse tomorrow's date.
- Reuse 7 PM.
- Reuse the duration.
- Set email = info@weaveapps.com.
- Continue booking.

AVAILABILITY FOLLOW-UP example:

Previous user:

"Show me available slots around 3 PM tomorrow."

Assistant:

"No available appointment slots were found."

Current user:

"How about 7 PM?"

This means:

"Show me available slots around 7 PM tomorrow."

Therefore:

- Reuse the previous date.
- Reuse the previous duration.
- Change ONLY the requested time.
- Keep auto_book = false.
- Do NOT require email.
- needs_slot_search = true.

Another availability example:

Previous:

"Show me available slots around 7 PM tomorrow."

Assistant:

"Here are the available slots..."

Current:

"How about 9 PM?"

This means:

"Show me available slots around 9 PM tomorrow."

The user is NOT booking yet.

Another example:

Previous:

"Show me available slots around 7 PM tomorrow."

Assistant:

"Here are the available slots..."

Current:

"7:30 PM"

Then the user is selecting one of the available
slots rather than creating an unrelated request.

==================================================
EMAIL RULE
==================================================

Do not invent an email address.

Reuse an email from previous conversation ONLY when
the current message clearly continues the pending
booking.

An email should not be copied from an unrelated old
appointment.

For availability-only requests:

- email is optional
- missing_fields must NOT contain email

==================================================
REQUEST TYPE
==================================================

Determine whether the user wants:

1. A new appointment to be BOOKED.

OR

2. ONLY availability information.

If the user only asks for available times:

- auto_book = false
- email is optional
- missing_fields must NOT contain email

If the user wants an appointment booked:

- auto_book = true
- email is required

==================================================
REQUIRED INFORMATION FOR BOOKING
==================================================

A booking requires:

- email
- date/time
- duration

The appointment title is OPTIONAL.

If no title is provided:

"title": "Appointment"

Do NOT add "title" to missing_fields.

If email is missing:

"email": null

and:

"missing_fields": ["email"]

If duration is missing:

Use 30 minutes.

==================================================
TITLE RULE
==================================================

If the user explicitly provides a title, use it.

Examples:

"Book a project meeting tomorrow at 7 PM"

→ title = "Project meeting"

"Book a doctor's appointment tomorrow at 7 PM"

→ title = "Doctor's appointment"

If no title is provided:

→ title = "Appointment"

Never add "title" to missing_fields.

==================================================
RETURN JSON
==================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "title": "Appointment",
    "email": null,
    "window_start": null,
    "window_end": null,
    "exact_start": null,
    "exact_end": null,
    "needs_slot_search": false,
    "auto_book": true,
    "duration_minutes": 30,
    "missing_fields": []
}}

==================================================
TIME RULES
==================================================

Use Asia/Colombo timezone (+05:30).

IMPORTANT DATE RULE:

The Python application is responsible for resolving
relative dates.

Do NOT perform date arithmetic.

Do NOT calculate "today".

Do NOT calculate "tomorrow".

Do NOT guess the calendar date.

For relative dates, extract the requested time normally.
The application will replace the calendar date after
the LLM response.

Examples:

"tomorrow at 7 PM"

Extract:

exact_start = the requested 7 PM time
exact_end = null

The Python application will assign the correct
calendar date and calculate exact_end from duration_minutes.

"today at 5 PM"

Extract the requested 5 PM time.

The Python application will assign today's date.

If the user specifies an explicit calendar date,
preserve that date.

For example:

"August 20 at 7 PM"

must use August 20.

Use Asia/Colombo timezone (+05:30).
If the user specifies an exact appointment time:

"Book tomorrow at 5 PM for 30 minutes"

use:

"exact_start": "...",
"exact_end": null,
"needs_slot_search": false

Python will calculate exact_end from exact_start
and duration_minutes.

If the user asks for a slot within a time window:

"Find me a 30-minute slot tomorrow afternoon"

use:

"window_start": "...",
"window_end": "...",
"needs_slot_search": true

If the user says "afternoon":

12:00 PM to 5:00 PM

If the user says "morning":

9:00 AM to 12:00 PM

If the user says "evening":

5:00 PM to 9:00 PM

If the user says "around [time]":

Treat it as a two-hour window centered around the
requested time.

Examples:

"around 7 PM"

→ 6:00 PM to 8:00 PM

"around 10 AM"

→ 9:00 AM to 11:00 AM

"around 2 PM"

→ 1:00 PM to 3:00 PM

"around 7:30 PM"

→ 6:30 PM to 8:30 PM

Do not return a window outside the requested range.

If duration is provided, use it.

If no duration is provided, use 30 minutes.

==================================================
AUTO BOOKING
==================================================

Set:

"auto_book": true

when the user wants the appointment booked.

Examples:

"Book an appointment tomorrow at 5 PM"

"Find me a slot tomorrow and book it"

"Book the first available slot"

Set:

"auto_book": false

when the user only wants availability.

Examples:

"Am I free tomorrow afternoon?"

"What times are available tomorrow?"

"Find me some available slots"

"Show me available slots around 7 PM"

==================================================
SLOT SEARCH
==================================================

Set:

"needs_slot_search": true

when the user wants to find an available slot.

Examples:

"Find me a slot"

"Find an available time"

"Find me a 30-minute slot tomorrow afternoon"

"Find me a slot around 7 PM"

"Book the first available slot"

Set:

"needs_slot_search": false

when the user specifies an exact time.

==================================================
EMAIL RULE
==================================================

If auto_book is true:

- email is required
- add "email" to missing_fields if it is not
  available from the current or pending booking context

If auto_book is false:

- email is optional
- DO NOT add "email" to missing_fields

==================================================
FINAL RULE
==================================================

Return JSON only.
"""

    # ========================================================
    # OPENAI REQUEST DIAGNOSTICS
    # ========================================================

    log_debug(
        logger,
        "OpenAI parser prompt characters:",
        len(prompt),
    )

    log_debug(
        logger,
        "Recent conversation messages:",
        len(recent_history),
    )

    # ========================================================
    # OPENAI REQUEST WITH RATE-LIMIT RETRY
    # ========================================================
    #
    # A transient 429 should not immediately fail the entire
    # booking workflow. Retry a small number of times with
    # exponential backoff.
    #
    # The prompt is also intentionally limited to recent
    # conversation history above so that normal booking
    # follow-ups consume substantially fewer tokens.
    #

    max_retries = 3

    response = None

    for attempt in range(
        max_retries
    ):

        try:

            response = client.chat.completions.create(
                model=AGENT_MODEL,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": prompt,
                    }
                ],
                response_format={
                    "type": "json_object"
                },
            )

            break

        except RateLimitError as exc:

            if attempt >= max_retries - 1:

                logger.exception(
                    "OpenAI rate limit exceeded after %s attempts.",
                    max_retries,
                )

                raise

            wait_seconds = (
                2 ** attempt
            )

            logger.warning(
                "OpenAI rate limit reached. "
                "Retrying in %s seconds "
                "(attempt %s/%s). Error: %s",
                wait_seconds,
                attempt + 1,
                max_retries,
                exc,
            )

            time.sleep(
                wait_seconds
            )

    if response is None:

        raise RuntimeError(
            "OpenAI request did not return a response."
        )

    data = json.loads(
        response.choices[0]
        .message
        .content
    )

    log_debug(logger,
        "\n=== RAW PARSER RESPONSE ==="
    )

    log_debug(logger,
        data
    )

    log_debug(logger,
        "===========================\n"
    )

    # ========================================================
    # NORMALIZE RESPONSE
    # ========================================================

    if "missing_fields" not in data:

        data["missing_fields"] = []

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    if not data.get("title"):

        data["title"] = "Appointment"

    if "title" in data["missing_fields"]:

        data["missing_fields"].remove(
            "title"
        )

    # --------------------------------------------------------
    # Duration
    # --------------------------------------------------------

    if not data.get(
        "duration_minutes"
    ):

        data["duration_minutes"] = 30

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    auto_book = data.get(
        "auto_book",
        True,
    )

    if auto_book:

        if not data.get(
            "email"
        ):

            if "email" not in data["missing_fields"]:

                data["missing_fields"].append(
                    "email"
                )

    else:

        if "email" in data["missing_fields"]:

            data["missing_fields"].remove(
                "email"
            )

    # ========================================================
    # DETERMINISTIC RELATIVE DATE CORRECTION
    # ========================================================

    data = _normalize_relative_dates(
        data,
        state["user_input"],
    )

    # ========================================================
# INHERIT DATE FROM PREVIOUS USER REQUEST
# ========================================================

    if conversation_history:

     previous_user_message = None

    current_input = (
        state["user_input"]
        .strip()
    )

    for message in reversed(
        conversation_history
    ):

        content = (
            message.get("content")
            or ""
        ).strip()

        # Skip the current user message.
        if (
            message.get("role") == "user"
            and content == current_input
        ):
            continue

        if (
            message.get("role") == "user"
            and content
        ):

            previous_user_message = content

            break

    if previous_user_message:

        current_text = (
            state["user_input"]
            .strip()
            .lower()
        )

        # Email follow-up
        #
        # Example:
        #
        # User:
        #   Book tomorrow at 1 PM
        #
        # Assistant:
        #   What email?
        #
        # User:
        #   info@weaveapps.com
        #
        # Reuse tomorrow from the previous request.

    if previous_user_message:

        current_text = (
            state["user_input"]
            .strip()
            .lower()
        )

        log_debug(logger, "\n=== DATE INHERIT DEBUG ===")
        log_debug(logger, "Current input:", state["user_input"])
        log_debug(logger, "Current text:", current_text)
        log_debug(logger, "Previous user message:", previous_user_message)
        log_debug(logger,
            "Has @:",
            "@" in current_text
        )
        log_debug(logger,
            "Has tomorrow:",
            "tomorrow" in previous_user_message.lower()
        )
        log_debug(logger,
            "Has today:",
            "today" in previous_user_message.lower()
        )
        log_debug(logger, "==========================\n")

        if (
            "@" in current_text
            and (
                "tomorrow"
                in previous_user_message.lower()
                or
                "today"
                in previous_user_message.lower()
            )
        ):

            data = _inherit_previous_relative_date(
                data,
                previous_user_message,
            )

            log_debug(logger,
                "\n=== INHERITED PREVIOUS DATE ==="
            )

            log_debug(logger,
                "Previous request:",
                previous_user_message,
            )

            log_debug(logger,
                "Normalized start:",
                data.get("exact_start"),
            )

            log_debug(logger,
                "Normalized end:",
                data.get("exact_end"),
            )

            log_debug(logger,
                "================================\n"
            )

            data = _inherit_previous_relative_date(
                data,
                previous_user_message,
            )

            log_debug(logger,
                "\n=== INHERITED PREVIOUS DATE ==="
            )

            log_debug(logger,
                "Previous request:",
                previous_user_message,
            )

            log_debug(logger,
                "Normalized start:",
                data.get("exact_start"),
            )

            log_debug(logger,
                "Normalized end:",
                data.get("exact_end"),
            )

            log_debug(logger,
                "================================\n"
            )

    # ========================================================
    # FOLLOW-UP TIME CORRECTION
    # ========================================================

    user_text = (
        state["user_input"]
        .strip()
        .lower()
    )

    follow_up_phrases = (
        "how about",
        "what about",
        "make it",
        "change it to",
        "move it to",
        "try",
    )

    is_time_follow_up = any(
        phrase in user_text
        for phrase in follow_up_phrases
    )

    previous_is_availability = (
        _is_availability_request(
            previous_user_message
        )
    )

    if is_time_follow_up:

        log_debug(logger,
            "\n=== TIME FOLLOW-UP DETECTED ==="
        )

        log_debug(logger,
            "Previous context:",
            previous_user_message,
        )

        log_debug(logger,
            "Current request:",
            state["user_input"],
        )

        log_debug(logger,
            "Previous was availability:",
            previous_is_availability,
        )

        log_debug(logger,
            "================================\n"
        )

        # ====================================================
        # AVAILABILITY FOLLOW-UP
        # ====================================================

        if previous_is_availability:

            log_debug(logger,
                "AVAILABILITY FOLLOW-UP"
            )

            # ------------------------------------------------
            # Reuse previous date
            # ------------------------------------------------

            data = _inherit_previous_relative_date(
                data,
                previous_user_message,
            )

            # ------------------------------------------------
            # Convert exact time into availability window
            # ------------------------------------------------

            data = (
                _convert_exact_time_to_availability_window(
                    data
                )
            )

            data["auto_book"] = False
            data["needs_slot_search"] = True

            # Email is not required for availability.
            data["email"] = None

            if "email" in data["missing_fields"]:

                data["missing_fields"].remove(
                    "email"
                )

        # ====================================================
        # BOOKING FOLLOW-UP
        # ====================================================

        else:

            log_debug(logger,
                "BOOKING FOLLOW-UP"
            )

            data = _inherit_previous_relative_date(
                data,
                previous_user_message,
            )

            data["auto_book"] = True

            if not data.get(
                "duration_minutes"
            ):

                data["duration_minutes"] = 30

    # ========================================================
    # DETERMINISTIC EXACT END TIME
    # ========================================================

    # Always calculate exact_end in Python for exact bookings.
    # This correctly handles appointments that cross midnight,
    # e.g. 11:30 PM + 30 minutes -> 12:00 AM next day.
    data = _calculate_exact_end(
        data
    )

    # ========================================================
    # FINAL NORMALIZATION
    # ========================================================

    if data.get(
        "auto_book",
        True,
    ):

        if not data.get(
            "email"
        ):

            if "email" not in data["missing_fields"]:

                data["missing_fields"].append(
                    "email"
                )

    else:

        if "email" in data["missing_fields"]:

            data["missing_fields"].remove(
                "email"
            )

    log_debug(logger,
        "\n=== PARSED REQUEST ==="
    )

    log_debug(logger,
        data
    )

    log_debug(logger,
        "======================\n"
    )

    return data


# ============================================================
# ROUTE AFTER PARSE
# ============================================================

def route_after_parse(
    state: BookingState
):

    if state.get(
        "missing_fields"
    ):

        return "request_missing_information"

    if state.get(
        "needs_slot_search"
    ):

        return "find_slots"

    return "check_exact_time"


# ============================================================
# REQUEST MISSING INFORMATION
# ============================================================

def request_missing_information(
    state: BookingState
):

    log_debug(logger,
        "\nNODE: request_missing_information"
    )

    missing_fields = state.get(
        "missing_fields",
        []
    )

    if "email" in missing_fields:

        message = (
            "What email address should I "
            "associate with the appointment?"
        )

    elif "duration_minutes" in missing_fields:

        message = (
            "How long should the appointment be?"
        )

    else:

        fields = ", ".join(
            missing_fields
        )

        message = (
            f"Please provide the following "
            f"information: {fields}."
        )

    final_response = {
        "success": False,
        "needs_input": True,
        "message": message,
    }

    log_debug(logger,
        "CLARIFICATION:",
        final_response
    )

    return {
        "final_response": final_response
    }


# ============================================================
# FIND SLOTS
# ============================================================

def find_slots(
    state: BookingState
):

    log_debug(logger,
        "\nNODE: find_slots"
    )


    result = find_available_slots(
        user_id=state["user_id"],
        window_start=state["window_start"],
        window_end=state["window_end"],
        duration_minutes=state[
            "duration_minutes"
        ],
    )

    log_debug(logger,
        "AVAILABLE SLOTS:",
        result
    )

    return {
        "available_slots": result.get(
            "available_slots",
            []
        )
    }


# ============================================================
# ROUTE AFTER SLOT SEARCH
# ============================================================

def route_after_slots(
    state: BookingState
):

    slots = state.get(
        "available_slots",
        []
    )

    if not slots:

        return "confirm"

    if state.get(
        "auto_book"
    ):

        return "select_slot"

    return "confirm"


# ============================================================
# SELECT SLOT
# ============================================================

def select_slot(
    state: BookingState
):

    log_debug(logger,
        "\nNODE: select_slot"
    )

    slots = state.get(
        "available_slots",
        []
    )

    if not slots:

        log_debug(logger,
            "NO AVAILABLE SLOTS"
        )

        return {
            "selected_slot": None
        }

    selected_slot = slots[0]

    log_debug(logger,
        "SELECTED SLOT:",
        selected_slot
    )

    return {
        "selected_slot": selected_slot
    }


# ============================================================
# CHECK EXACT TIME
# ============================================================

def check_exact_time(
    state: BookingState
):

    log_debug(logger,
        "\nNODE: check_exact_time"
    )

    start = state.get(
        "exact_start"
    )

    end = state.get(
        "exact_end"
    )

    if not start or not end:

        return {
            "booking_result": {
                "success": False,
                "error": (
                    "Exact appointment time "
                    "is missing."
                ),
            }
        }

    try:

        start_dt = datetime.fromisoformat(
            start
        )

        end_dt = datetime.fromisoformat(
            end
        )

        if end_dt <= start_dt:

            log_debug(logger,
                "INVALID TIME RANGE:",
                start,
                "->",
                end,
            )

            return {
                "booking_result": {
                    "success": False,
                    "error": (
                        "Invalid appointment time range."
                    ),
                }
            }

        result = check_availability(
            user_id=state["user_id"],
            start=start,
            end=end,
        )

    except Exception as e:

        log_debug(logger,
            "AVAILABILITY ERROR:",
            str(e)
        )

        return {
            "booking_result": {
                "success": False,
                "error": str(e),
            }
        }

    log_debug(logger,
        "AVAILABILITY RESULT:",
        result
    )

    # --------------------------------------------------------
    # Calendar service error
    # --------------------------------------------------------

    if result.get(
        "error"
    ):

        return {
            "booking_result": {
                "success": False,
                "error": result["error"],
            }
        }

    # --------------------------------------------------------
    # Available
    # --------------------------------------------------------

    if result.get(
        "available"
    ):

        log_debug(logger,
            "REQUESTED TIME IS AVAILABLE"
        )

        return {
            "selected_slot": {
                "start": start,
                "end": end,
            }
        }

    # --------------------------------------------------------
    # Not available
    # --------------------------------------------------------

    log_debug(logger,
        "REQUESTED TIME IS NOT AVAILABLE"
    )

    return {
        "selected_slot": None,
        "booking_result": {
            "success": False,
            "error": (
                "The requested time is not available."
            ),
        },
    }


# ============================================================
# ROUTE AFTER EXACT TIME
# ============================================================

def route_after_exact_time(
    state: BookingState
):

    booking_result = state.get(
        "booking_result"
    )

    if booking_result:

        if not booking_result.get(
            "success",
            False,
        ):

            return "confirm"

    if state.get(
        "selected_slot"
    ):

        if state.get(
            "auto_book",
            True,
        ):

            return "book_appointment"

    return "confirm"


# ============================================================
# BOOK APPOINTMENT
# ============================================================

def book_appointment(
    state: BookingState
):

    log_debug(logger,
        "\nNODE: book_appointment"
    )

    selected_slot = state.get(
        "selected_slot"
    )

    if not selected_slot:

        log_debug(logger,
            "NO SLOT TO BOOK"
        )

        return {
            "booking_result": {
                "success": False,
                "error": (
                    "No available slot was found."
                ),
            }
        }

    # --------------------------------------------------------
    # Safety check
    # --------------------------------------------------------

    email = state.get(
        "email"
    )

    if not email:

        log_debug(logger,
            "NO EMAIL - BOOKING BLOCKED"
        )

        return {
            "booking_result": {
                "success": False,
                "error": (
                    "An email address is required "
                    "before booking."
                ),
            }
        }

    result = create_event(
        user_id=state["user_id"],
        title=state.get(
            "title",
            "Appointment"
        ),
        start=selected_slot["start"],
        end=selected_slot["end"],
        email=email,
    )

    log_debug(logger,
        "BOOKING RESULT:",
        result
    )

    return {
        "booking_result": result
    }


# ============================================================
# CONFIRM
# ============================================================

def confirm(
    state: BookingState
):

    log_debug(logger,
        "\nNODE: confirm"
    )

    result = state.get(
        "booking_result"
    )

    # --------------------------------------------------------
    # Successful booking
    # --------------------------------------------------------

    if result and result.get(
        "success"
    ):

        selected_slot = state.get(
            "selected_slot"
        )

        final_response = {
            "success": True,
            "message": (
                "Your appointment has been "
                "successfully booked."
            ),
            "event_id": result.get(
                "event_id"
            ),
            "link": result.get(
                "link"
            ),
            "start": (
                selected_slot.get("start")
                if selected_slot
                else None
            ),
            "end": (
                selected_slot.get("end")
                if selected_slot
                else None
            ),
        }

    # --------------------------------------------------------
    # Failed booking
    # --------------------------------------------------------

    elif result:

        final_response = {
            "success": False,
            "message": result.get(
                "error",
                "Unable to complete the appointment."
            ),
        }

    # --------------------------------------------------------
    # Availability only
    # --------------------------------------------------------

    else:

        slots = state.get(
            "available_slots",
            []
        )

        if slots:

            final_response = {
                "success": True,
                "message": (
                    "Available appointment slots "
                    "were found."
                ),
                "slots": slots,
                "available_slots": slots,
            }

        else:

            final_response = {
                "success": False,
                "message": (
                    "No available appointment slots "
                    "were found."
                ),
                "slots": [],
                "available_slots": [],
            }

    log_debug(logger,
        "FINAL RESPONSE:",
        final_response
    )

    return {
        "final_response": final_response
    }


# ============================================================
# GRAPH
# ============================================================

graph_builder = StateGraph(
    BookingState
)


# ============================================================
# NODES
# ============================================================

graph_builder.add_node(
    "parse_request",
    parse_request,
)

graph_builder.add_node(
    "request_missing_information",
    request_missing_information,
)

graph_builder.add_node(
    "find_slots",
    find_slots,
)

graph_builder.add_node(
    "select_slot",
    select_slot,
)

graph_builder.add_node(
    "check_exact_time",
    check_exact_time,
)

graph_builder.add_node(
    "book_appointment",
    book_appointment,
)

graph_builder.add_node(
    "confirm",
    confirm,
)


# ============================================================
# START
# ============================================================

graph_builder.add_edge(
    START,
    "parse_request",
)


# ============================================================
# PARSE ROUTING
# ============================================================

graph_builder.add_conditional_edges(
    "parse_request",
    route_after_parse,
    {
        "request_missing_information":
            "request_missing_information",

        "find_slots":
            "find_slots",

        "check_exact_time":
            "check_exact_time",
    },
)


# ============================================================
# MISSING INFORMATION → END
# ============================================================

graph_builder.add_edge(
    "request_missing_information",
    END,
)


# ============================================================
# SLOT SEARCH ROUTING
# ============================================================

graph_builder.add_conditional_edges(
    "find_slots",
    route_after_slots,
    {
        "select_slot":
            "select_slot",

        "confirm":
            "confirm",
    },
)


# ============================================================
# SELECT SLOT → BOOK
# ============================================================

graph_builder.add_edge(
    "select_slot",
    "book_appointment",
)


# ============================================================
# EXACT TIME ROUTING
# ============================================================

graph_builder.add_conditional_edges(
    "check_exact_time",
    route_after_exact_time,
    {
        "book_appointment":
            "book_appointment",

        "confirm":
            "confirm",
    },
)


# ============================================================
# BOOK → CONFIRM
# ============================================================

graph_builder.add_edge(
    "book_appointment",
    "confirm",
)


# ============================================================
# CONFIRM → END
# ============================================================

graph_builder.add_edge(
    "confirm",
    END,
)


# ============================================================
# COMPILE
# ============================================================

booking_graph = (
    graph_builder.compile()
)