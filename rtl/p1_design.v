module seq_detector_0011(
    input clk,
    input reset,
    input data_in,
    output reg detected
);

    reg [2:0] history;
    reg match_dly;

    always @(posedge clk) begin
        if (reset || (^history === 1'bx) || (match_dly === 1'bx)) begin
            history <= 3'b000;
            match_dly <= 1'b0;
        end else begin
            match_dly <= ({history, data_in} == 4'b0011);
            history <= {history[1:0], data_in};
        end
    end

    always @(*) begin
        if (reset) begin
            detected = 1'b0;
        end else begin
            detected = (match_dly == 1'b1);
        end
    end

endmodule
