import SpotCard from "./SpotCard";
import SpotModal from "./SpotModal";
import { useState } from "react";

function ParkingGrid({
  balance,
  setBalance,
  setHistory
}) {

  const reservationCost = 10;

  // Search + filter state
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  // Selected modal spot ID
  const [selectedSpotId, setSelectedSpotId] = useState(null);

  // Parking spots
  const [spots, setSpots] = useState([
    { id: 1, status: "available" },
    { id: 2, status: "occupied" },
    { id: 3, status: "reserved" }
  ]);

  // Get latest selected spot
  const selectedSpot = spots.find(
    (spot) => spot.id === selectedSpotId
  );

  // Time formatter
  const getCurrentTime = () => {

    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit"
    });

  };

  // Reserve spot
  const reserveSpot = (id) => {

    if (balance < reservationCost) {
      alert("Not enough balance!");
      return;
    }

    const updatedSpots = spots.map((spot) => {

      if (spot.id === id && spot.status === "available") {
        return { ...spot, status: "reserved" };
      }

      return spot;
    });

    setSpots(updatedSpots);

    // Deduct balance
    setBalance(balance - reservationCost);

    // Update history
    setHistory((prevHistory) => [
      `🟡 Reserved Spot ${id} - ${getCurrentTime()}`,
      ...prevHistory
    ]);
  };

  // Cancel reservation
  const cancelReservation = (id) => {

    const updatedSpots = spots.map((spot) => {

      if (spot.id === id && spot.status === "reserved") {
        return { ...spot, status: "available" };
      }

      return spot;
    });

    setSpots(updatedSpots);

    // Refund balance
    setBalance(balance + reservationCost);

    // Update history
    setHistory((prevHistory) => [
      `❌ Cancelled Spot ${id} - ${getCurrentTime()}`,
      ...prevHistory
    ]);
  };

  // Filtered spots
  const filteredSpots = spots.filter((spot) => {

    const matchesSearch =
      spot.id.toString().includes(search);

    const matchesFilter =
      filter === "all" || spot.status === filter;

    return matchesSearch && matchesFilter;

  });

  // Statistics
  const availableCount = spots.filter(
    (spot) => spot.status === "available"
  ).length;

  const occupiedCount = spots.filter(
    (spot) => spot.status === "occupied"
  ).length;

  const reservedCount = spots.filter(
    (spot) => spot.status === "reserved"
  ).length;

  // Statistics card style
  const cardStyle = {
    backgroundColor: "white",
    padding: "15px 20px",
    borderRadius: "10px",
    boxShadow: "0 4px 10px rgba(0,0,0,0.08)",
    fontWeight: "bold"
  };

  return (
    <>

      {/* Search + Filter */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "15px",
          marginBottom: "25px",
          flexWrap: "wrap"
        }}
      >

        <input
          type="text"
          placeholder="Search Spot ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: "10px",
            borderRadius: "8px",
            border: "1px solid #ccc"
          }}
        />

        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{
            padding: "10px",
            borderRadius: "8px",
            border: "1px solid #ccc"
          }}
        >
          <option value="all">All Spots</option>
          <option value="available">Available</option>
          <option value="occupied">Occupied</option>
          <option value="reserved">Reserved</option>
        </select>

      </div>

      {/* Statistics */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "20px",
          marginBottom: "25px",
          flexWrap: "wrap"
        }}
      >

        <div style={cardStyle}>
          🟢 Available: {availableCount}
        </div>

        <div style={cardStyle}>
          🔴 Occupied: {occupiedCount}
        </div>

        <div style={cardStyle}>
          🟡 Reserved: {reservedCount}
        </div>

      </div>

      {/* Parking Grid */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          flexWrap: "wrap",
          gap: "30px",
          marginTop: "30px"
        }}
      >

        {filteredSpots.map((spot) => (
          <div
            key={spot.id}
            onClick={() => setSelectedSpotId(spot.id)}
            style={{ cursor: "pointer" }}
          >

            <SpotCard
              id={spot.id}
              status={spot.status}
              reserveSpot={reserveSpot}
              cancelReservation={cancelReservation}
            />

          </div>
        ))}

      </div>

      {/* Spot Modal */}
      <SpotModal
        spot={selectedSpot}
        onClose={() => setSelectedSpotId(null)}
        reserveSpot={reserveSpot}
        cancelReservation={cancelReservation}
      />

    </>
  );
}

export default ParkingGrid;