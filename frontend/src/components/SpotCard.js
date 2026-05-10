function SpotCard({
  id,
  status,
  reserveSpot,
  cancelReservation
}) {

  // Card color
  const getColor = () => {
    if (status === "available") return "green";
    if (status === "occupied") return "red";
    if (status === "reserved") return "yellow";

    return "gray";
  };

  // Text color
  const getTextColor = () => {
    return status === "reserved" ? "black" : "white";
  };

  // Format text
  const formatStatus = () => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  return (
    <div
      style={{
        backgroundColor: getColor(),
        padding: "25px",
        borderRadius: "10px",
        width: "160px",
        textAlign: "center",
        color: getTextColor(),
        fontWeight: "bold",
        boxShadow: "0 4px 8px rgba(0,0,0,0.2)"
      }}
    >

      <p>Spot {id}</p>

      <p>{formatStatus()}</p>

      {/* Reserve Button */}
      {status === "available" && (
        <button
          onClick={() => reserveSpot(id)}
          style={{
            marginTop: "10px",
            padding: "8px 14px",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "bold"
          }}
        >
          Reserve
        </button>
      )}

      {/* Cancel Button */}
      {status === "reserved" && (
        <button
          onClick={() => cancelReservation(id)}
          style={{
            marginTop: "10px",
            padding: "8px 14px",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "bold"
          }}
        >
          Cancel
        </button>
      )}

    </div>
  );
}

export default SpotCard;