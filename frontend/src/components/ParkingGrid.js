import SpotCard from "./SpotCard";
import { useState } from "react";

function ParkingGrid() {

  const [spots, setSpots] = useState([
    { id: 1, status: "available" },
    { id: 2, status: "occupied" },
    { id: 3, status: "reserved" }
  ]);

  // Reserve parking spot
  const reserveSpot = (id) => {

    const updatedSpots = spots.map((spot) => {

      if (spot.id === id && spot.status === "available") {
        return { ...spot, status: "reserved" };
      }

      return spot;
    });

    setSpots(updatedSpots);
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
  };

  return (
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
        <SpotCard
          key={spot.id}
          id={spot.id}
          status={spot.status}
          reserveSpot={reserveSpot}
          cancelReservation={cancelReservation}
        />
      ))}

    </div>
  );
}

export default ParkingGrid;