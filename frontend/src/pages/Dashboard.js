import ParkingGrid from "../components/ParkingGrid";
import Navbar from "../components/Navbar";
import { useState } from "react";

function Dashboard() {

  const [balance, setBalance] = useState(0);
  const [amount, setAmount] = useState("");

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
          background: "linear-gradient(to right, #f5f7fa, #e4ecf7)"
        }}
      >

        <h1 style={{ marginBottom: "10px" }}>
          ParkReserve Dashboard
        </h1>

        {/* Wallet Card */}
        <div
          style={{
            backgroundColor: "white",
            width: "350px",
            margin: "20px auto",
            padding: "25px",
            borderRadius: "12px",
            boxShadow: "0 4px 10px rgba(0,0,0,0.1)"
          }}
        >

          <h2 style={{ marginBottom: "10px" }}>
            Welcome, Riya 👋
          </h2>

          <h3 style={{ marginBottom: "20px" }}>
            Balance: ${balance}
          </h3>

          <p style={{ color: "gray" }}>
          Reservation Cost: $10
          </p>
          
          <input
            type="number"
            placeholder="Enter amount"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
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

        {/* Legend */}
        <div style={{ marginBottom: "30px" }}>
          <span style={{ marginRight: "15px" }}>🟢 Available</span>
          <span style={{ marginRight: "15px" }}>🔴 Occupied</span>
          <span>🟡 Reserved</span>
        </div>

        {/* Parking Grid */}
        <ParkingGrid
          balance={balance}
          setBalance={setBalance}
        />

      </div>
    </>
  );
}

export default Dashboard;