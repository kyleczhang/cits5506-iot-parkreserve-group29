import SpotCard from "./SpotCard";
import SpotModal from "./SpotModal";
import { useState } from "react";

function ParkingGrid({
  balance,
  setBalance,
  setHistory
}) {

  const reservationCost = 10;

  // Selected spot for modal
  const [selectedSpot, setSelectedSpot] = useState(null);

  // Parking spots
  const [spots, setSpots] = useState([
    { id: 1, status: "available" },
    { id: 2, status: "occupied" },
    { id: 3, status: "reserved" }
  ]);

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

    // Update selected modal spot
    setSelectedSpot(
      updatedSpots.find((spot) => spot.id === id)
    );

    // Deduct balance
    setBalance(balance - reservationCost);

    // Update activity
    setHistory((prevHistory) => [
      `🟡 Reserved Spot ${id}`,
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

    // Update selected modal spot
    setSelectedSpot(
      updatedSpots.find((spot) => spot.id === id)
    );

    // Refund balance
    setBalance(balance + reservationCost);

    // Update activity
    setHistory((prevHistory) => [
      `❌ Cancelled Spot ${id}`,
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
            onClick={() => setSelectedSpot(spot)}
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
        onClose={() => setSelectedSpot(null)}
        reserveSpot={reserveSpot}
        cancelReservation={cancelReservation}
      />
    </>
  );
}

export default ParkingGrid;