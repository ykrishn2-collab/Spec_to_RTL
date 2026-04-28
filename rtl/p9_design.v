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
  logic signed [ACC_WIDTH-1:0]    sum_next;

  always_comb begin
    sum_next = '0;
    for (int i = 0; i < N; i = i + 1) begin
      if (i == 0) begin
        sum_next = sum_next + ACC_WIDTH'(x_in * h[i]);
      end else begin
        sum_next = sum_next + ACC_WIDTH'(sample_reg[i-1] * h[i]);
      end
    end
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      sample_reg <= '0;
      y_out      <= '0;
    end else begin
      sample_reg[0] <= x_in;
      for (int i = 1; i < N; i = i + 1) begin
        sample_reg[i] <= sample_reg[i-1];
      end
      y_out <= sum_next;
    end
  end

endmodule
