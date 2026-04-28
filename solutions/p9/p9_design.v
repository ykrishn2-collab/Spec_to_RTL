module fir_filter #(
  parameter WIDTH = 16,
  parameter N = 8
) (
  input  logic                             clk,
  input  logic                             rst,
  input  logic signed [WIDTH-1:0]          x_in,
  input  logic signed [N-1:0][WIDTH-1:0]   h,
  output logic signed [2*WIDTH+$clog2(N):0] y_out
);

  localparam int ACC_WIDTH = 2 * WIDTH + $clog2(N) + 1;
  localparam int NUM_STAGES = (N > 1) ? (N - 1) : 1;

  logic signed [2*WIDTH-1:0] mult_terms [0:N-1];
  logic signed [ACC_WIDTH-1:0] state_regs [0:NUM_STAGES-1];
  integer i;

  always_comb begin
    for (i = 0; i < N; i = i + 1) begin
      mult_terms[i] = x_in * h[i];
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      y_out <= '0;
      for (i = 0; i < NUM_STAGES; i = i + 1) begin
        state_regs[i] <= '0;
      end
    end else begin
      if (N == 1) begin
        y_out <= mult_terms[0];
      end else begin
        y_out <= mult_terms[0] + state_regs[0];
        for (i = 0; i < N-2; i = i + 1) begin
          state_regs[i] <= mult_terms[i+1] + state_regs[i+1];
        end
        state_regs[N-2] <= mult_terms[N-1];
      end
    end
  end

endmodule
