import { useNavigate } from "react-router-dom";

export default function NewSessionButton() {
  const navigate = useNavigate();
  return (
    <button className="primary new-session" onClick={() => navigate("/session/new")}>
      <span aria-hidden="true">＋</span> Start session
    </button>
  );
}
