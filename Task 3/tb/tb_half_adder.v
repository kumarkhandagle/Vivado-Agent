
module tb_top;

    reg a, b;
    wire sum, carry;

    integer passed = 0;
    integer failed = 0;
    integer i;
    integer hit;

    // Coverage flags for four input combinations
    integer cov00 = 0;
    integer cov01 = 0;
    integer cov10 = 0;
    integer cov11 = 0;

    // DUT
    half_adder dut (
        .a(a),
        .b(b),
        .sum(sum),
        .carry(carry)
    );

    initial begin

        // Apply all input combinations
        for (i = 0; i < 4; i = i + 1) begin

            {a, b} = i;
            #10;

            // Functional coverage
            if (a == 0 && b == 0)
                cov00 = 1;

            if (a == 0 && b == 1)
                cov01 = 1;

            if (a == 1 && b == 0)
                cov10 = 1;

            if (a == 1 && b == 1)
                cov11 = 1;

            // Self-checking logic
            if ((sum === (a ^ b)) &&
                (carry === (a & b)))
                passed = passed + 1;
            else
                failed = failed + 1;

        end

        // Calculate functional coverage
        hit = cov00 + cov01 + cov10 + cov11;

        // Final simulation summary
        $display("TESTS_PASSED: %0d", passed);
        $display("TESTS_FAILED: %0d", failed);
        $display("COVERAGE: %0d%%", hit * 100 / 4);

        if (failed == 0 && hit == 4)
            $display("ALL TESTS PASSED");

        $finish;
    end

endmodule
