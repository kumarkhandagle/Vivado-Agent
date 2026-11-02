
`timescale 1ns/1ps

module tb_top;

    reg a;
    reg b;
    reg cin;

    wire sum;
    wire cout;

    integer passed = 0;
    integer failed = 0;
    integer errors = 0;
    integer previous_errors;
    integer i;
    integer hit;

    // Functional coverage
    reg [7:0] input_cov = 8'b0;

    // DUT
    full_adder dut (
        .a    (a),
        .b    (b),
        .cin  (cin),
        .sum  (sum),
        .cout (cout)
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

    // Full adder verification
    task check_adder;
        input [2:0] test_vector;

        reg [1:0] expected;

        begin
            {a, b, cin} = test_vector;

            #1;

            // Calculate expected result
            expected = {1'b0, a} +
                       {1'b0, b} +
                       {1'b0, cin};

            // Functional coverage
            input_cov[test_vector] = 1'b1;

            // Compare actual and expected outputs
            if ({cout, sum} !== expected) begin
                errors = errors + 1;

                $display(
                    "ERROR: A=%b B=%b CIN=%b expected_sum=%b expected_cout=%b actual_sum=%b actual_cout=%b at %0t",
                    a, b, cin,
                    expected[0], expected[1],
                    sum, cout, $time
                );
            end
        end
    endtask

    initial begin

        // Initialization
        a = 1'b0;
        b = 1'b0;
        cin = 1'b0;

        // ST_01: All inputs LOW
        previous_errors = errors;

        check_adder(3'b000);

        finish_test(1, previous_errors);

        // ST_02: Only carry input HIGH
        previous_errors = errors;

        check_adder(3'b001);

        finish_test(2, previous_errors);

        // ST_03: Only B HIGH
        previous_errors = errors;

        check_adder(3'b010);

        finish_test(3, previous_errors);

        // ST_04: B and CIN HIGH
        previous_errors = errors;

        check_adder(3'b011);

        finish_test(4, previous_errors);

        // ST_05: Only A HIGH
        previous_errors = errors;

        check_adder(3'b100);

        finish_test(5, previous_errors);

        // ST_06: A and CIN HIGH
        previous_errors = errors;

        check_adder(3'b101);

        finish_test(6, previous_errors);

        // ST_07: Remaining input combinations
        previous_errors = errors;

        check_adder(3'b110);
        check_adder(3'b111);

        finish_test(7, previous_errors);

        // Calculate functional coverage
        hit = 0;

        for (i = 0; i < 8; i = i + 1)
            if (input_cov[i])
                hit = hit + 1;

        // Final simulation summary
        $display("TESTS_PASSED: %0d", passed);
        $display("TESTS_FAILED: %0d", failed);
        $display("COVERAGE: %0d%%", hit * 100 / 8);

        if (passed == 7 &&
            failed == 0 &&
            errors == 0 &&
            hit == 8)
            $display("ALL TESTS PASSED");
        else
            $display("SMOKE TEST FAILED");

        $finish;
    end

endmodule
