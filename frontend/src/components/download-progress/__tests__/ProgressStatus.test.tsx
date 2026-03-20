import { render, screen } from "@testing-library/react";

import { ProgressStatus } from "../ProgressStatus";

describe("ProgressStatus", () => {
  it("shows a cancelled summary state", () => {
    render(
      <ProgressStatus
        currentLabel="cancelled"
        progressPercent={0}
        progress={{
          status: "cancelled",
          job_id: "job-1",
          error: "Download cancelled by user",
          code: "download_cancelled",
        }}
      />,
    );

    expect(screen.getByText("Descarga cancelada.")).toBeInTheDocument();
    expect(screen.getByText(/estado: cancelado/i)).toBeInTheDocument();
  });
});
