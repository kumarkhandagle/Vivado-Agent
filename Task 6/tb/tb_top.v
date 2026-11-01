
`timescale 1ns/1ps

module tb_top;

    reg clk;
    reg rst;
    reg d;

    wire q;

    integer passed = 0;
    integer failed = 0;
    integer errors = 0;
    integer previous_errors;
    integer i;
    integer hit;

    // Functional coverage
    reg [7:0] input_cov = 8'b0;

    // DUT
    d_flipflop dut (
        .clk (clk),
        .rst (rst),
        .d   (d),
        .q   (q)
    );

    // Error reporting
    task report_error;
        input [255:0] message;
        begin
            errors = errors + 1;
            $display("ERROR: %0s at %0t", message, $time);
        end
    endtask

    // Test result reporting
    task finish_test;
        input integer test_number;
        input integer error_count_before;
        begin
            if (errors == error_count_before) begin
                passed = passed + 1;
                $display("ST_%02d: PASS", test_number);
            end
            else begin
                failed = failed + 1;
                $display("ST_%02d: FAIL", test_number);
            end
        end
    endtask

    // D flip-flop verification
    task check_dff;
        input expected;
        input [255:0] message;

        begin
            #1;

            // Compare actual and expected outputs
            if (q !== expected) begin
                $display(
                    "CLK=%b RST=%b D=%b expected_q=%b actual_q=%b",
                    clk, rst, d, expected, q
                );

                report_error(message);
            end
        end
    endtask

    initial begin

        // Initialization
        clk = 1'b0;
        rst = 1'b0;
        d   = 1'b0;

        #1;

        // ST_01: Asynchronous reset when clock is LOW
        previous_errors = errors;

        rst = 1'b1;

        check_dff(1'b0, "Asynchronous reset failed");

        input_cov[0] = 1'b1;

        finish_test(1, previous_errors);

        // ST_02: Reset active during rising clock edge
        previous_errors = errors;

        d = 1'b1;

        #1;
        clk = 1'b1;

        check_dff(1'b0, "Reset priority failed");

        input_cov[1] = 1'b1;

        finish_test(2, previous_errors);

        // ST_03: Reset deassertion without rising edge
        previous_errors = errors;

        rst = 1'b0;

        check_dff(1'b0, "Output changed after reset release");

        clk = 1'b0;

        check_dff(1'b0, "Output changed at falling edge");

        input_cov[2] = 1'b1;

        finish_test(3, previous_errors);

        // ST_04: Capture HIGH input at rising edge
        previous_errors = errors;

        d = 1'b1;

        #1;
        clk = 1'b1;

        check_dff(1'b1, "Failed to capture HIGH input");

        input_cov[3] = 1'b1;

        finish_test(4, previous_errors);

        // ST_05: Input changes without clock edge
        previous_errors = errors;

        d = 1'b0;

        check_dff(1'b1, "Output changed without clock edge");

        input_cov[4] = 1'b1;

        finish_test(5, previous_errors);

        // ST_06: Falling edge should not update output
        previous_errors = errors;

        clk = 1'b0;

        check_dff(1'b1, "Output changed at falling edge");

        input_cov[5] = 1'b1;

        finish_test(6, previous_errors);

        // ST_07: Capture LOW input at rising edge
        previous_errors = errors;

        clk = 1'b1;

        check_dff(1'b0, "Failed to capture LOW input");

        input_cov[6] = 1'b1;

        finish_test(7, previous_errors);

        // ST_08: Asynchronous reset when clock is HIGH
        previous_errors = errors;

        clk = 1'b0;
        d   = 1'b1;

        #1;
        clk = 1'b1;

        check_dff(1'b1, "Failed to capture HIGH before reset");

        rst = 1'b1;

        check_dff(1'b0, "Asynchronous reset failed when clock HIGH");

        input_cov[7] = 1'b1;

        finish_test(8, previous_errors);

        // Calculate functional coverage
        hit = 0;

        for (i = 0; i < 8; i = i + 1)
            if (input_cov[i])
                hit = hit + 1;

        // Final simulation summary
        $display("TESTS_PASSED: %0d", passed);
        $display("TESTS_FAILED: %0d", failed);
        $display("COVERAGE: %0d%%", hit * 100 / 8);

        if (passed == 8 &&
            failed == 0 &&
            errors == 0 &&
            hit == 8)
            $display("ALL TESTS PASSED");
        else
            $display("SMOKE TEST FAILED");

        $finish;
    end

endmodule
