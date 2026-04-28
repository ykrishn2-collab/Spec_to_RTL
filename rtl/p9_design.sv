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

  logic signed [N-1:0][WIDTH-1:0] sample_reg;
  logic signed [N-1:0][WIDTH-1:0] sample_next;
  logic signed [ACC_WIDTH-1:0]    acc_next;

  always_comb begin
    int i;
    sample_next    = sample_reg;
    sample_next[0] = x_in;
    for (i = 1; i < N; i = i + 1) begin
      sample_next[i] = sample_reg[i-1];
    end
  end

  always_comb begin
    int i;
    acc_next = '0;
    for (i = 0; i < N; i = i + 1) begin
      acc_next = acc_next + (sample_next[i] * h[i]);
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      sample_reg <= '0;
      y_out      <= '0;
    end else begin
      sample_reg <= sample_next;
      y_out      <= acc_next;
    end
  end

endmodule
