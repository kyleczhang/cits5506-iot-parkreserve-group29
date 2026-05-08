import ParkingGrid from "../components/ParkingGrid";

function Dashboard() {
  return (
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

      <div style={{ marginBottom: "30px" }}>
        <span style={{ marginRight: "15px" }}>🟢 Available</span>
        <span style={{ marginRight: "15px" }}>🔴 Occupied</span>
        <span>🟡 Reserved</span>
      </div>

      <ParkingGrid />
    </div>
  );
}

export default Dashboard;