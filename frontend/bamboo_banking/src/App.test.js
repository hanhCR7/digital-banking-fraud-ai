import { render, screen } from "@testing-library/react";
import App from "./App";

jest.mock("./routes/Router", () => function MockRouter() {
  return <div>Mock Router</div>;
});

test("renders app shell", () => {
  render(<App />);
  expect(screen.getByText("Mock Router")).toBeInTheDocument();
});
