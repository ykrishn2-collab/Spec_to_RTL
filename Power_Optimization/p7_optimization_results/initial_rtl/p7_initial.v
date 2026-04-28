module exp_fixed_point #(
  parameter WIDTH = 8
) (
  input  logic               clk,
  input  logic               rst,
  input  logic               enable,
  input  logic [WIDTH-1:0]   x_in,
  output logic [2*WIDTH-1:0] exp_out
);

  localparam integer FRAC_BITS = WIDTH - 1;

  logic [WIDTH-1:0]     x_pipe;
  logic [2*WIDTH-1:0]   x_sq_pipe;
  logic                 valid_pipe;

  logic [3*WIDTH-1:0]   x_cu_full;
  logic [2*WIDTH-1:0]   term_x2;
  logic [2*WIDTH-1:0]   term_x3;
  logic [2*WIDTH-1:0]   exp_sum;

  always_comb begin
    x_cu_full = x_sq_pipe * x_pipe;
    term_x2   = x_sq_pipe >> FRAC_BITS;
    term_x2   = term_x2 >> 1;
    term_x3   = x_cu_full >> (2 * FRAC_BITS);
    term_x3   = term_x3 / 6;

    exp_sum   = { {(2*WIDTH-WIDTH){1'b0}}, x_pipe };
    exp_sum   = exp_sum + ({{(2*WIDTH-1){1'b0}}, 1'b1} << FRAC_BITS);
    exp_sum   = exp_sum + term_x2;
    exp_sum   = exp_sum + term_x3;
  end

  always_ff @(posedge clk) begin
    if (rst) begin
      x_pipe     <= '0;
      x_sq_pipe  <= '0;
      valid_pipe <= 1'b0;
      exp_out    <= '0;
    end else begin
      if (enable) begin
        x_pipe     <= x_in;
        x_sq_pipe  <= x_in * x_in;
        valid_pipe <= 1'b1;
      end

      if (valid_pipe) begin
        exp_out <= exp_sum;
      end
    end
  end

endmodule
