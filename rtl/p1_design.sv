module seq_detector_0011(
    input clk,
    input reset,
    input data_in,
    output reg detected
);

    localparam [1:0] S_IDLE = 2'd0;
    localparam [1:0] S_0    = 2'd1;
    localparam [1:0] S_00   = 2'd2;
    localparam [1:0] S_001  = 2'd3;

    reg [1:0] state;

    always @(posedge clk) begin
        if (reset) begin
            state    <= S_IDLE;
            detected <= 1'b0;
        end else begin
            detected <= 1'b0;

            case (state)
                S_IDLE: begin
                    if (data_in)
                        state <= S_IDLE;
                    else
                        state <= S_0;
                end

                S_0: begin
                    if (data_in)
                        state <= S_IDLE;
                    else
                        state <= S_00;
                end

                S_00: begin
                    if (data_in)
                        state <= S_001;
                    else
                        state <= S_00;
                end

                S_001: begin
                    if (data_in) begin
                        state    <= S_IDLE;
                        detected <= 1'b1;
                    end else begin
                        state <= S_0;
                    end
                end

                default: begin
                    state <= S_IDLE;
                end
            endcase
        end
    end

endmodule
