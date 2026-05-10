import { Link } from "react-router-dom";

function Navbar() {
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
      <div style={{ display: "flex", alignItems: "center" }}>

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

        <Link
          to="/"
          style={{
            color: "white",
            textDecoration: "none",
            fontWeight: "bold"
          }}
        >
          Logout
        </Link>

      </div>
    </nav>
  );
}

export default Navbar;