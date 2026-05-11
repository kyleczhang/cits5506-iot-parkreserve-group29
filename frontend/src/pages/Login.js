import { Link, useNavigate } from "react-router-dom";
import { API_ENDPOINTS } from "../services/api";

function Login() {

  const navigate = useNavigate();

  const handleLogin = async () => {

    try {

      const response = await fetch(
        API_ENDPOINTS.login,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            email: "demo@parkreserve.com",
            password: "password123"
          })
        }
      );

      console.log(
        "Login response status:",
        response.status
      );

      // Temporary frontend navigation
      navigate("/dashboard");

    } catch (error) {

      console.log(
        "Backend not connected yet:",
        error
      );

      // Allow frontend demo workflow
      navigate("/dashboard");

    }

  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(to right, #f5f7fa, #e4ecf7)"
      }}
    >
      <div
        style={{
          backgroundColor: "white",
          padding: "40px",
          borderRadius: "12px",
          width: "320px",
          boxShadow: "0 4px 10px rgba(0,0,0,0.1)",
          textAlign: "center"
        }}
      >
        <h1 style={{ marginBottom: "25px" }}>
          ParkReserve Login
        </h1>

        <input
          type="email"
          placeholder="Email"
          style={{
            width: "100%",
            padding: "12px",
            marginBottom: "15px",
            borderRadius: "8px",
            border: "1px solid #ccc"
          }}
        />

        <input
          type="password"
          placeholder="Password"
          style={{
            width: "100%",
            padding: "12px",
            marginBottom: "20px",
            borderRadius: "8px",
            border: "1px solid #ccc"
          }}
        />

        <button
          onClick={handleLogin}
          style={{
            width: "100%",
            padding: "12px",
            backgroundColor: "#0077cc",
            color: "white",
            border: "none",
            borderRadius: "8px",
            cursor: "pointer",
            fontWeight: "bold"
          }}
        >
          Login
        </button>

        <p style={{ marginTop: "20px" }}>
          Don’t have an account?{" "}
          <Link to="/register">Register</Link>
        </p>

      </div>
    </div>
  );
}

export default Login;