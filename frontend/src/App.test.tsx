import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";

const ready = {
  mode: "fixture",
  database: "ready",
  collection: "disabled",
  notifications: "disabled",
};
function response(value: unknown) {
  return { ok: true, json: async () => value };
}

describe("workspace connection states", () => {
  it("shows an honest empty fixture state without provider data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(ready)));
    render(<App />);
    expect(await screen.findByText("No collected activity yet")).toBeVisible();
    expect(screen.getByText("Fixture mode")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Connected");
  });
  it("recovers from an unreachable API on retry without displaying raw errors", async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new Error("https://key:DO_NOT_LOG@host"))
      .mockResolvedValue(response(ready));
    vi.stubGlobal("fetch", fetcher);
    render(<App />);
    expect(await screen.findByText("Your workspace is offline")).toBeVisible();
    expect(screen.queryByText(/DO_NOT_LOG/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Try again/ }));
    expect(await screen.findByText("No collected activity yet")).toBeVisible();
  });
  it("distinguishes a reachable API from an unavailable database", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ ...ready, database: "unavailable" })),
    );
    render(<App />);
    expect(await screen.findByText(/its database is unavailable/)).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Offline");
  });
  it("does not treat a malformed response as a ready workspace", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ mode: "fixture", secret: "DO_NOT_LOG" })),
    );
    render(<App />);
    expect(await screen.findByText("Your workspace is offline")).toBeVisible();
    expect(screen.queryByText("Fixture mode")).not.toBeInTheDocument();
  });
});
