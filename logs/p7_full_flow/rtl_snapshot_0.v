module exp_fixed_point #(
  parameter WIDTH = 8
) (
  input  logic               clk,
  input  logic               rst,
  input  logic               enable,
  input  logic [WIDTH-1:0]   x_in,
  output logic [2*WIDTH-1:0] exp_out
);

  localparam int FRAC = WIDTH - 1;
  localparam int X2W  = 2 * WIDTH;
  localparam int X3W  = 3 * WIDTH;
  localparam logic [2*WIDTH-1:0] ONE_FIXED = {{(2*WIDTH-FRAC-1){1'b0}}, 1'b1, {FRAC{1'b0}}};

  logic                  stage1_valid;
  logic                  stage2_valid;
  logic [WIDTH-1:0]      x_s1;
  logic [WIDTH+1:0]      x2_scaled_s1;
  logic [WIDTH+2:0]      x3_scaled_s1;

  logic [X2W-1:0]        x2_full;
  logic [X3W-1:0]        x3_full;
  logic [WIDTH+1:0]      x2_scaled_next;
  logic [WIDTH+2:0]      x3_scaled_next;
  logic [2*WIDTH-1:0]    sum_stage2;
  logic [2*WIDTH-1:0]    x_term_ext;
  logic [2*WIDTH-1:0]    x2_term_ext;
  logic [2*WIDTH-1:0]    x3_term_ext;

  assign x2_full = x_in * x_in;
  assign x3_full = x2_full * x_in;

  generate
    if (FRAC > 0) begin : gen_frac_shift
      assign x2_scaled_next = (x2_full + ({{(X2W-1){1'b0}}, 1'b1} << (FRAC - 1))) >> FRAC;
      assign x3_scaled_next = (x3_full + ({{(X3W-1){1'b0}}, 1'b1} << (2*FRAC - 1))) >> (2*FRAC);
    end else begin : gen_int_shift
      assign x2_scaled_next = x2_full[WIDTH+1:0];
      assign x3_scaled_next = x3_full[WIDTH+2:0];
    end
  endgenerate

  assign x_term_ext  = {{WIDTH{1'b0}}, x_s1};
  assign x2_term_ext = {{(WIDTH-2){1'b0}}, ((x2_scaled_s1 + 1'b1) >> 1)};
  assign x3_term_ext = {{(WIDTH-3){1'b0}}, ((x3_scaled_s1 + 3'd3) / 3'd6)};

  assign sum_stage2 = (ONE_FIXED + x_term_ext) + (x2_term_ext + x3_term_ext);

  always_ff @(posedge clk) begin
    if (rst) begin
      stage1_valid  <= 1'b0;
      stage2_valid  <= 1'b0;
      x_s1          <= '0;
      x2_scaled_s1  <= '0;
      x3_scaled_s1  <= '0;
      exp_out       <= '0;
    end else begin
      stage2_valid <= stage1_valid;

      if (enable) begin
        stage1_valid <= 1'b1;
        x_s1         <= x_in;
        x2_scaled_s1 <= x2_scaled_next;
        x3_scaled_s1 <= x3_scaled_next;
      end else begin
        stage1_valid <= 1'b0;
      end

      if (stage2_valid) begin
        exp_out <= sum_stage2;
      end
    end
  end

endmodule
