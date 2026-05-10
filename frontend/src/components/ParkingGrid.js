import SpotCard from "./SpotCard";
import SpotModal from "./SpotModal";
import { useState } from "react";

function ParkingGrid({
  balance,
  setBalance,
  setHistory
}) {

  const reservationCost = 10;

  // Time formatter
  const getCurrentTime = () => {

    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit"
    });

  };

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

  return (
    <>
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          flexWrap: "wrap",
          gap: "30px",
          marginTop: "30px"
        }}
      >

        {spots.map((spot) => (
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

      {/* Modal */}
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