module seq_detector_0011(
    input clk,
    input reset,
    input data_in,
    output reg detected
);
    reg [2:0] state;

    localparam [2:0] S_IDLE = 3'b000;
    localparam [2:0] S_0    = 3'b001;
    localparam [2:0] S_00   = 3'b010;
    localparam [2:0] S_001  = 3'b011;
    localparam [2:0] S_DET  = 3'b100;

    always @(posedge clk) begin
        if (reset) begin
            state    <= S_IDLE;
            detected <= 1'b0;
        end else begin
            detected <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (data_in) begin
                        state <= S_IDLE;
                    end else begin
                        state <= S_0;
                    end
                end

                S_0: begin
                    if (data_in) begin
                        state <= S_IDLE;
                    end else begin
                        state <= S_00;
                    end
                end

                S_00: begin
                    if (data_in) begin
                        state <= S_001;
                    end else begin
                        state <= S_00;
                    end
                end

                S_001: begin
                    if (data_in) begin
                        state <= S_DET;
                    end else begin
                        state <= S_00;
                    end
                end

                default: begin
                    detected <= 1'b1;
                    if (data_in) begin
                        state <= S_IDLE;
                    end else begin
                        state <= S_0;
                    end
                end
            endcase
        end
    end

endmodule
