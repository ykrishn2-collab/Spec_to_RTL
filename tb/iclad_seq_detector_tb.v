`timescale 1ns/1ps

module tb;
    reg clk, reset, data_in;
    wire detected;

    seq_detector_0011 dut (
        .clk(clk),
        .reset(reset),
        .data_in(data_in),
        .detected(detected)
    );

    initial clk = 0;
    always #0.5 clk = ~clk;

    integer i;
    reg [15:0] test_input  = 16'b0001100110110010;
    reg [15:0] test_output = 16'b0000010001000000;
    reg expected, actual;
    integer errors;

    initial begin
        errors = 0;
        reset = 1; data_in = 0;
        repeat(3) @(posedge clk); #0.1;
        reset = 0;

        for (i = 15; i >= 0; i = i - 1) begin
            data_in = test_input[i];
            @(posedge clk); #0.1;
            expected = test_output[i];
            actual   = detected;
            if (actual !== expected) begin
                $display("MISMATCH at bit %0d: expected=%b got=%b",
                          i, expected, actual);
                errors = errors + 1;
            end
        end

        if (errors == 0)
            $display("PASS");
        else
            $display("FAIL: %0d mismatches", errors);

        $finish;
    end

    initial begin
        #10000;
        $display("FAIL: timeout");
        $finish;
    end
endmodule