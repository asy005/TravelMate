import { useContext } from "react";
import { AuthContext } from "./AuthContext";

const RequireAuth = ({ children }: any) => {
  const { token } = useContext(AuthContext);

  if (!token) window.location.href = "/login";
  return children;
};

export default RequireAuth;
