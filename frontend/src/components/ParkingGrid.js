import SpotCard from "./SpotCard";

function ParkingGrid() {
  const spots = [
    { id: 1, status: "available" },
    { id: 2, status: "occupied" },
    { id: 3, status: "reserved" }
  ];

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        gap: "30px",
        marginTop: "30px"
      }}
    >
      {spots.map((spot) => (
        <SpotCard key={spot.id} id={spot.id} status={spot.status} />
      ))}
    </div>
  );
}

export default ParkingGrid;