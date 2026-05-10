import ParkingGrid from "../components/ParkingGrid";
import Navbar from "../components/Navbar";
import { useState } from "react";

function Dashboard() {

  // Wallet balance
  const [balance, setBalance] = useState(0);

  // Input amount
  const [amount, setAmount] = useState("");

  // Dynamic reservation history
  const [history, setHistory] = useState([]);

  // Get registered vehicle plate
  const vehiclePlate =
    localStorage.getItem("vehiclePlate");

  // Add credits
  const addCredits = () => {

    if (amount === "") return;

    setBalance(balance + Number(amount));
    setAmount("");
  };

  return (
    <>
      <Navbar />

      <div
        style={{
          textAlign: "center",
          minHeight: "100vh",
          paddingTop: "30px",
          background:
            "linear-gradient(to right, #f5f7fa, #e4ecf7)"
        }}
      >

        {/* Title */}
        <h1 style={{ marginBottom: "10px" }}>
          ParkReserve Dashboard
        </h1>

        {/* Top Cards */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "stretch",
            gap: "25px",
            flexWrap: "wrap",
            marginTop: "30px",
            marginBottom: "40px"
          }}
        >

          {/* Wallet Card */}
          <div
            style={{
              backgroundColor: "white",
              width: "320px",
              minHeight: "260px",
              padding: "25px",
              borderRadius: "12px",
              boxShadow:
                "0 6px 14px rgba(0,0,0,0.08)"
            }}
          >

            <h2 style={{ marginBottom: "10px" }}>
              Welcome, Riya 👋
            </h2>

            <h3 style={{ marginBottom: "10px" }}>
              Balance: ${balance}
            </h3>

            <p
              style={{
                color: "gray",
                marginBottom: "20px"
              }}
            >
              Reservation Cost: $10
            </p>

            <input
              type="number"
              placeholder="Enter amount"
              value={amount}
              onChange={(e) =>
                setAmount(e.target.value)
              }
              style={{
                width: "80%",
                padding: "10px",
                marginBottom: "15px",
                borderRadius: "8px",
                border: "1px solid #ccc"
              }}
            />

            <br />

            <button
              onClick={addCredits}
              style={{
                padding: "12px 20px",
                backgroundColor: "#0077cc",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "bold"
              }}
            >
              Add Credits
            </button>

          </div>

          {/* User Profile */}
          <div
            style={{
              backgroundColor: "white",
              width: "320px",
              minHeight: "260px",
              padding: "25px",
              borderRadius: "12px",
              boxShadow:
                "0 6px 14px rgba(0,0,0,0.08)",
              textAlign: "left"
            }}
          >

            <h2 style={{ marginBottom: "15px" }}>
              User Profile
            </h2>

            <p>
              <strong>Name:</strong> Riya Sakhiya
            </p>

            <p>
              <strong>Email:</strong>
              {" "}riya@example.com
            </p>

            <p>
              <strong>Registered Vehicle:</strong>
              {" "}
              {vehiclePlate || "Not Registered"}
            </p>

            <p style={{ marginTop: "15px" }}>
              <strong>LPR Status:</strong>
              {" "}
              Ready for validation
            </p>

          </div>

          {/* Activity Card */}
          <div
            style={{
              backgroundColor: "white",
              width: "320px",
              minHeight: "260px",
              padding: "25px",
              borderRadius: "12px",
              boxShadow:
                "0 6px 14px rgba(0,0,0,0.08)",
              textAlign: "left"
            }}
          >

            <h2 style={{ marginBottom: "15px" }}>
              Recent Activity
            </h2>

            {history.length > 0 ? (
              <ul style={{ paddingLeft: "20px" }}>
                {history.map((item, index) => (
                  <li
                    key={index}
                    style={{
                      marginBottom: "12px"
                    }}
                  >
                    {item}
                  </li>
                ))}
              </ul>
            ) : (
              <p>No recent activity</p>
            )}

          </div>

        </div>

        {/* Legend */}
        <div style={{ marginBottom: "30px" }}>
          <span style={{ marginRight: "15px" }}>
            🟢 Available
          </span>

          <span style={{ marginRight: "15px" }}>
            🔴 Occupied
          </span>

          <span>
            🟡 Reserved
          </span>
        </div>

        {/* Parking Grid */}
        <ParkingGrid
          balance={balance}
          setBalance={setBalance}
          setHistory={setHistory}
        />

      </div>
    </>
  );
}

export default Dashboard;