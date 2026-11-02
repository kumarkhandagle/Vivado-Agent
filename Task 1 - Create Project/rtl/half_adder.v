//////////////////Design Code:
module apb_m (
    input             pclk,
    input             presetn,
    input      [3:0]  addrin,
    input      [31:0] datain,
    input             wr,
    input             newd,
    input      [3:0]  strbin,
    input      [31:0] prdata,
    input             pready,
    input             pslverr,

    output reg        psel,
    output reg        penable,
    output reg        slverr,
    output reg [3:0]  paddr,
    output reg [31:0] pwdata,
    output reg        pwrite,
    output reg [3:0]  pstrb,
    output reg [31:0] dataout
);

    localparam [1:0] idle   = 2'd0,
                     setup  = 2'd1,
                     enable = 2'd2;

    reg [1:0]  state, nstate;
    reg [3:0]  addr_reg;
    reg [31:0] data_reg;
    reg        wr_reg;
    reg [3:0]  strb_reg;


    // Block 1: State, request capture, and response capture
    always @(posedge pclk or negedge presetn)
    begin
        if (!presetn)
        begin
            state    <= idle;
            addr_reg <= 4'h0;
            data_reg <= 32'h00000000;
            wr_reg   <= 1'b0;
            strb_reg <= 4'b0000;
            slverr   <= 1'b0;
            dataout  <= 32'h00000000;
        end
        else
        begin
            state <= nstate;

            // Capture the next request when entering SETUP.
            // Hold these values throughout ACCESS and wait states.
            if (nstate == setup)
            begin
                addr_reg <= addrin;
                data_reg <= datain;
                wr_reg   <= wr;
                strb_reg <= wr ? strbin : 4'b0000;
            end

            // Capture the response at transfer completion.
            if (psel && penable && pready)
            begin
                // Hold the latest completed transfer's error status.
                slverr <= pslverr;

                // Update read data only for a successful read.
                if (!pwrite && !pslverr)
                    dataout <= prdata;
            end
        end
    end


    // Block 2: Next-state decoder
    always @(*)
    begin
        nstate = idle;

        case (state)
            idle:
            begin
                if (newd)
                    nstate = setup;
                else
                    nstate = idle;
            end

            setup:
            begin
                nstate = enable;
            end

            enable:
            begin
                if (!pready)
                    nstate = enable;
                else if (newd)
                    nstate = setup;
                else
                    nstate = idle;
            end

            default:
                nstate = idle;
        endcase
    end


    // Block 3: Combinational output decoder
    always @(*)
    begin
        psel    = 1'b0;
        penable = 1'b0;
        paddr   = 4'h0;
        pwdata  = 32'h00000000;
        pwrite  = 1'b0;
        pstrb   = 4'b0000;

        case (state)
            idle:
            begin
                // Defaults provide IDLE outputs.
            end

            setup, enable:
            begin
                psel    = 1'b1;
                penable = (state == enable);
                paddr   = addr_reg;
                pwrite  = wr_reg;
                pwdata  = wr_reg ? data_reg : 32'h00000000;
                pstrb   = wr_reg ? strb_reg : 4'b0000;
            end

            default:
            begin
                // Defaults handle invalid states.
            end
        endcase
    end

endmodule///////////////////TB Code:
`timescale 1ns/1ps

`timescale 1ns/1ps

module tb_m;

    reg        pclk;
    reg        presetn;
    reg [3:0]  addrin;
    reg [31:0] datain;
    reg        wr;
    reg        newd;
    reg [3:0]  strbin;
    reg [31:0] prdata;
    reg        pready;
    reg        pslverr;

    wire        psel;
    wire        penable;
    wire        slverr;
    wire [3:0]  paddr;
    wire [31:0] pwdata;
    wire        pwrite;
    wire [3:0]  pstrb;
    wire [31:0] dataout;

    apb_m dut (
        .pclk(pclk),
        .presetn(presetn),
        .addrin(addrin),
        .datain(datain),
        .wr(wr),
        .newd(newd),
        .strbin(strbin),
        .prdata(prdata),
        .pready(pready),
        .pslverr(pslverr),
        .psel(psel),
        .penable(penable),
        .slverr(slverr),
        .paddr(paddr),
        .pwdata(pwdata),
        .pwrite(pwrite),
        .pstrb(pstrb),
        .dataout(dataout)
    );

    always #10 pclk = ~pclk;

    // Issue one request and provide a controlled slave response.
    task transfer;
        input        req_wr;
        input [3:0]  req_addr;
        input [31:0] req_data;
        input [3:0]  req_strb;
        input integer wait_cycles;
        input        response_error;
        input [31:0] response_data;

        reg [3:0]  expected_strb;
        reg [31:0] expected_data;
        reg [31:0] previous_read;
        reg        previous_error;
        integer i;

        begin
            @(negedge pclk);

            previous_read  = dataout;
            previous_error = slverr;
            expected_strb  = req_wr ? req_strb : 4'b0000;
            expected_data  = req_wr ? req_data : 32'h00000000;

            addrin  = req_addr;
            datain  = req_data;
            wr      = req_wr;
            strbin  = req_strb;
            newd    = 1'b1;
            pready  = 1'b0;
            pslverr = response_error;
            prdata  = response_data;

            // Request has entered SETUP.
            @(negedge pclk);
            newd = 1'b0;

            if ({psel, penable, paddr, pwrite, pstrb, pwdata} !==
                {1'b1, 1'b0, req_addr, req_wr,
                 expected_strb, expected_data})
            begin
                $display("FAIL: SETUP signals mismatch");
                $finish;
            end

            // Request has entered ACCESS.
            @(negedge pclk);

            // Keep PREADY low for the requested wait cycles.
            for (i = 0; i < wait_cycles; i = i + 1)
            begin
                @(posedge pclk);

                if ({psel, penable, paddr, pwrite, pstrb, pwdata} !==
                    {1'b1, 1'b1, req_addr, req_wr,
                     expected_strb, expected_data})
                begin
                    $display("FAIL: Request changed during wait state");
                    $finish;
                end

                @(negedge pclk);

                if ((slverr !== previous_error) ||
                    (dataout !== previous_read))
                begin
                    $display("FAIL: Response captured before completion");
                    $finish;
                end
            end

            // Complete the transfer at the next rising edge.
            pready = 1'b1;
            @(posedge pclk);

            if ({psel, penable, paddr, pwrite, pstrb, pwdata} !==
                {1'b1, 1'b1, req_addr, req_wr,
                 expected_strb, expected_data})
            begin
                $display("FAIL: ACCESS signals mismatch at completion");
                $finish;
            end

            // Allow registered responses to update.
            @(negedge pclk);

            if (slverr !== response_error)
            begin
                $display("FAIL: Slave error capture mismatch");
                $finish;
            end

            if (!req_wr && !response_error)
            begin
                if (dataout !== response_data)
                begin
                    $display("FAIL: Read data mismatch: %h", dataout);
                    $finish;
                end
            end
            else if (dataout !== previous_read)
            begin
                $display("FAIL: Write or failed read changed dataout");
                $finish;
            end

            pready  = 1'b0;
            pslverr = 1'b0;

            $display("PASS: wr=%b addr=%h strb=%b waits=%0d error=%b",
                     req_wr, req_addr, expected_strb,
                     wait_cycles, response_error);
        end
    endtask

    initial begin
        pclk    = 1'b0;
        presetn = 1'b0;
        addrin  = 4'h0;
        datain  = 32'h00000000;
        wr      = 1'b0;
        newd    = 1'b0;
        strbin  = 4'b0000;
        prdata  = 32'h00000000;
        pready  = 1'b0;
        pslverr = 1'b0;

        repeat (5) @(negedge pclk);
        presetn = 1'b1;

        // Arguments:
        // write, address, data, strobes, waits, error, read response

        // Full-word write.
        transfer(1'b1, 4'h4, 32'h11223344, 4'b1111,
                 0, 1'b0, 32'h00000000);

        // Write byte [15:8], with two wait states.
        transfer(1'b1, 4'h4, 32'h0000AA00, 4'b0010,
                 2, 1'b0, 32'h00000000);

        // Successful read: PSTRB must be zero despite STRBIN=1111.
        transfer(1'b0, 4'h4, 32'h00000000, 4'b1111,
                 1, 1'b0, 32'hAABBCCDD);

        // Failed read: retain the previous DATAOUT.
        transfer(1'b0, 4'h4, 32'h00000000, 4'b0000,
                 2, 1'b1, 32'hDEADBEEF);

        // Failed write: capture error and preserve DATAOUT.
        transfer(1'b1, 4'h8, 32'h12345678, 4'b1111,
                 0, 1'b1, 32'h00000000);

        // Successful read clears the previously captured error.
        transfer(1'b0, 4'h4, 32'h00000000, 4'b0000,
                 0, 1'b0, 32'h55667788);

        $display("PASS: All tests completed");
        $finish;
    end

    // Watchdog.
    initial begin
        #5000;
        $display("FAIL: Testbench timeout");
        $finish;
    end

endmodule