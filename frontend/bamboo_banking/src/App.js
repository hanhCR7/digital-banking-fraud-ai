import "./index.css";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import Router from "./routes/Router";

function App() {
  return (
    <>
      <Router />
      <ToastContainer position="top-right" autoClose={4000} theme="colored" />
    </>
  );
}

export default App;
