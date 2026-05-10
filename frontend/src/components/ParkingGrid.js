import SpotCard from "./SpotCard";
import { useState } from "react";

function ParkingGrid({ balance, setBalance }) {

  const [spots, setSpots] = useState([
    { id: 1, status: "available" },
    { id: 2, status: "occupied" },
    { id: 3, status: "reserved" }
  ]);

  const reservationCost = 10;

  // Reserve parking spot
  const reserveSpot = (id) => {

  // Prevent reservation if insufficient balance
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
};

  const cancelReservation = (id) => {

  const updatedSpots = spots.map((spot) => {

    if (spot.id === id && spot.status === "reserved") {
      return { ...spot, status: "available" };
    }

    return spot;
  });

  setSpots(updatedSpots);

  // Refund credits
  setBalance(balance + reservationCost);
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