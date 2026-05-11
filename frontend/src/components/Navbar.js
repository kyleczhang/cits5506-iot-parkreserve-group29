import { Link, useNavigate } from "react-router-dom";

function Navbar() {

  const navigate = useNavigate();

  const handleLogout = () => {

    // Clear stored user session data
    localStorage.removeItem("vehiclePlate");

    navigate("/");

  };

  return (
    <nav
      style={{
        backgroundColor: "#0077cc",
        padding: "15px 30px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        color: "white",
        boxShadow: "0 2px 8px rgba(0,0,0,0.1)"
      }}
    >

      {/* Left Side */}
      <div
        style={{
          display: "flex",
          alignItems: "center"
        }}
      >

        <img
          src="/logo.png"
          alt="logo"
          style={{
            width: "40px",
            marginRight: "10px"
          }}
        />

        <h2 style={{ margin: 0 }}>
          ParkReserve
        </h2>

      </div>

      {/* Right Side */}
      <div>

        <Link
          to="/dashboard"
          style={{
            color: "white",
            textDecoration: "none",
            marginRight: "20px",
            fontWeight: "bold"
          }}
        >
          Dashboard
        </Link>

        <button
          onClick={handleLogout}
          style={{
            background: "none",
            border: "none",
            color: "white",
            fontWeight: "bold",
            cursor: "pointer",
            fontSize: "16px"
          }}
        >
          Logout
        </button>

      </div>

    </nav>
  );
}

export default Navbar;