function ParkingGrid() {
  const spots = [
    { id: 1, status: "available" },
    { id: 2, status: "occupied" },
    { id: 3, status: "reserved" }
  ];

  return (
    <div>
      {spots.map((spot) => (
        <div key={spot.id}>
          Spot {spot.id} - {spot.status}
        </div>
      ))}
    </div>
  );
}

export default ParkingGrid;