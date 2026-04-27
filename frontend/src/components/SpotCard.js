function SpotCard({ id, status }) {

  const getColor = () => {
    if (status === "available") return "green";
    if (status === "occupied") return "red";
    if (status === "reserved") return "yellow";
    return "gray";
  };

  const getTextColor = () => {
    return status === "reserved" ? "black" : "white";
  };

  const formatStatus = () => {
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  return (
    <div
      style={{
        backgroundColor: getColor(),
        padding: "25px",
        borderRadius: "10px",
        width: "140px",
        textAlign: "center",
        color: getTextColor(),
        fontWeight: "bold",
        boxShadow: "0 4px 8px rgba(0,0,0,0.2)"
      }}
    >
      <p>Spot {id}</p>
      <p>{formatStatus()}</p>
    </div>
  );
}

export default SpotCard;