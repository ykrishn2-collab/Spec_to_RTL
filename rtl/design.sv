module fir_filter #(
  parameter WIDTH = 16,
  parameter N = 8
) (
  input  logic                              clk,
  input  logic                              rst,
  input  logic signed [WIDTH-1:0]           x_in,
  input  logic signed [N-1:0][WIDTH-1:0]    h,
  output logic signed [2*WIDTH+$clog2(N):0] y_out
);

  localparam ACC_WIDTH = 2 * WIDTH + $clog2(N) + 1;

  logic signed [N-1:0][WIDTH-1:0] samples;
  logic signed [N-1:0][WIDTH-1:0] next_samples;
  logic signed [ACC_WIDTH-1:0] acc_comb;
  integer i;

  always @(*) begin
    next_samples = samples;
    next_samples[0] = x_in;
    for (i = 1; i < N; i = i + 1) begin
      next_samples[i] = samples[i-1];
    end
  end

  always @(*) begin
    acc_comb = '0;
    for (i = 0; i < N; i = i + 1) begin
      acc_comb = acc_comb + (next_samples[i] * h[i]);
    end
  end

  always @(posedge clk) begin
    if (rst) begin
      samples <= '0;
      y_out <= '0;
    end else begin
      samples <= next_samples;
      y_out <= acc_comb;
    end
  end

endmodule
