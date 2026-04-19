import './App.css';
import ParkingGrid from './components/ParkingGrid';

function App() {
  return (
    <div style={{ textAlign: "center", paddingTop: "30px" }}>
      <h1>ParkReserve Dashboard</h1>
      <div style={{ marginTop: "10px" }}>
        <span style={{ marginRight: "15px" }}>🟢 Available</span>
        <span style={{ marginRight: "15px" }}>🔴 Occupied</span>
        <span>🟡 Reserved</span>
      </div>
      <ParkingGrid />
    </div>
  );
}

export default App;