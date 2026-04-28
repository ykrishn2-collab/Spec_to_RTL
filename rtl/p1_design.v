module seq_detector_0011(
    input clk,
    input reset,
    input data_in,
    output reg detected
);

    reg [3:0] shift_reg;

    always @(posedge clk) begin
        if (reset) begin
            shift_reg <= 4'b0000;
            detected <= 1'b0;
        end else begin
            detected <= (shift_reg == 4'b0011);
            shift_reg <= {shift_reg[2:0], data_in};
        end
    end

endmodule
