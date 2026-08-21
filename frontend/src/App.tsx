import {
  useEffect,
  useState,
} from "react";

import Chat from "./Chat";
import Login from "./Login";

import {
  getCurrentUser,
  logout,
} from "./api";

import "./App.css";

type User = {
  id: number;
  email: string;
  name?: string;
};

export default function App() {

  const [
    authenticated,
    setAuthenticated,
  ] = useState<boolean | null>(null);

  const [
    user,
    setUser,
  ] = useState<User | null>(null);


  // ==========================================================
  // CHECK SESSION
  // ==========================================================

  useEffect(() => {

    const checkAuthentication =
      async () => {

        try {

          const result =
            await getCurrentUser();

          if (
            result.authenticated
          ) {

            setUser(
              result.user ?? null
            );

            setAuthenticated(
              true
            );

          } else {

            setUser(null);

            setAuthenticated(
              false
            );
          }

        } catch (error) {

          console.error(
            "Authentication check failed:",
            error
          );

          setUser(null);

          setAuthenticated(
            false
          );
        }
      };

    checkAuthentication();

  }, []);


  // ==========================================================
  // LOGOUT
  // ==========================================================

  const handleLogout =
    async () => {

      try {

        await logout();

      } catch (error) {

        console.error(
          "Logout failed:",
          error
        );
      }

      setUser(null);

      setAuthenticated(
        false
      );
    };


  // ==========================================================
  // LOADING
  // ==========================================================

  if (
    authenticated === null
  ) {

    return (
      <div className="auth-loading">
        Checking authentication...
      </div>
    );
  }


  // ==========================================================
  // LOGIN
  // ==========================================================

  if (!authenticated) {

    return <Login />;
  }


  // ==========================================================
  // CHAT
  // ==========================================================

  return (
    <Chat
      user={user}
      onLogout={handleLogout}
    />
  );
}