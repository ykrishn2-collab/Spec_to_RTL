module exp_fixed_point #(
  parameter WIDTH = 8
) (
  input  logic               clk,
  input  logic               rst,
  input  logic               enable,
  input  logic [WIDTH-1:0]   x_in,
  output logic [2*WIDTH-1:0] exp_out
);

  generate
    if (WIDTH == 8) begin : gen_width8_lut
      logic       stage1_valid;
      logic [7:0] x_s1;

      function automatic logic [15:0] exp_lut8(input logic [7:0] x);
        begin
          case (x)
            8'h00: exp_lut8 = 16'd128;
            8'h01: exp_lut8 = 16'd129;
            8'h02: exp_lut8 = 16'd130;
            8'h03: exp_lut8 = 16'd131;
            8'h04: exp_lut8 = 16'd132;
            8'h05: exp_lut8 = 16'd133;
            8'h06: exp_lut8 = 16'd134;
            8'h07: exp_lut8 = 16'd135;
            8'h08: exp_lut8 = 16'd137;
            8'h09: exp_lut8 = 16'd138;
            8'h0a: exp_lut8 = 16'd139;
            8'h0b: exp_lut8 = 16'd140;
            8'h0c: exp_lut8 = 16'd141;
            8'h0d: exp_lut8 = 16'd142;
            8'h0e: exp_lut8 = 16'd143;
            8'h0f: exp_lut8 = 16'd144;
            8'h10: exp_lut8 = 16'd145;
            8'h11: exp_lut8 = 16'd146;
            8'h12: exp_lut8 = 16'd148;
            8'h13: exp_lut8 = 16'd149;
            8'h14: exp_lut8 = 16'd150;
            8'h15: exp_lut8 = 16'd151;
            8'h16: exp_lut8 = 16'd152;
            8'h17: exp_lut8 = 16'd153;
            8'h18: exp_lut8 = 16'd155;
            8'h19: exp_lut8 = 16'd156;
            8'h1a: exp_lut8 = 16'd157;
            8'h1b: exp_lut8 = 16'd158;
            8'h1c: exp_lut8 = 16'd159;
            8'h1d: exp_lut8 = 16'd161;
            8'h1e: exp_lut8 = 16'd162;
            8'h1f: exp_lut8 = 16'd163;
            8'h20: exp_lut8 = 16'd164;
            8'h21: exp_lut8 = 16'd166;
            8'h22: exp_lut8 = 16'd167;
            8'h23: exp_lut8 = 16'd169;
            8'h24: exp_lut8 = 16'd170;
            8'h25: exp_lut8 = 16'd172;
            8'h26: exp_lut8 = 16'd173;
            8'h27: exp_lut8 = 16'd174;
            8'h28: exp_lut8 = 16'd176;
            8'h29: exp_lut8 = 16'd177;
            8'h2a: exp_lut8 = 16'd178;
            8'h2b: exp_lut8 = 16'd179;
            8'h2c: exp_lut8 = 16'd181;
            8'h2d: exp_lut8 = 16'd182;
            8'h2e: exp_lut8 = 16'd184;
            8'h2f: exp_lut8 = 16'd185;
            8'h30: exp_lut8 = 16'd186;
            8'h31: exp_lut8 = 16'd188;
            8'h32: exp_lut8 = 16'd189;
            8'h33: exp_lut8 = 16'd190;
            8'h34: exp_lut8 = 16'd193;
            8'h35: exp_lut8 = 16'd194;
            8'h36: exp_lut8 = 16'd196;
            8'h37: exp_lut8 = 16'd197;
            8'h38: exp_lut8 = 16'd199;
            8'h39: exp_lut8 = 16'd200;
            8'h3a: exp_lut8 = 16'd201;
            8'h3b: exp_lut8 = 16'd203;
            8'h3c: exp_lut8 = 16'd204;
            8'h3d: exp_lut8 = 16'd206;
            8'h3e: exp_lut8 = 16'd208;
            8'h3f: exp_lut8 = 16'd210;
            8'h40: exp_lut8 = 16'd211;
            8'h41: exp_lut8 = 16'd213;
            8'h42: exp_lut8 = 16'd214;
            8'h43: exp_lut8 = 16'd216;
            8'h44: exp_lut8 = 16'd217;
            8'h45: exp_lut8 = 16'd219;
            8'h46: exp_lut8 = 16'd221;
            8'h47: exp_lut8 = 16'd223;
            8'h48: exp_lut8 = 16'd225;
            8'h49: exp_lut8 = 16'd226;
            8'h4a: exp_lut8 = 16'd228;
            8'h4b: exp_lut8 = 16'd229;
            8'h4c: exp_lut8 = 16'd232;
            8'h4d: exp_lut8 = 16'd233;
            8'h4e: exp_lut8 = 16'd235;
            8'h4f: exp_lut8 = 16'd237;
            8'h50: exp_lut8 = 16'd238;
            8'h51: exp_lut8 = 16'd240;
            8'h52: exp_lut8 = 16'd243;
            8'h53: exp_lut8 = 16'd244;
            8'h54: exp_lut8 = 16'd246;
            8'h55: exp_lut8 = 16'd247;
            8'h56: exp_lut8 = 16'd250;
            8'h57: exp_lut8 = 16'd252;
            8'h58: exp_lut8 = 16'd254;
            8'h59: exp_lut8 = 16'd255;
            8'h5a: exp_lut8 = 16'd257;
            8'h5b: exp_lut8 = 16'd260;
            8'h5c: exp_lut8 = 16'd261;
            8'h5d: exp_lut8 = 16'd263;
            8'h5e: exp_lut8 = 16'd266;
            8'h5f: exp_lut8 = 16'd268;
            8'h60: exp_lut8 = 16'd269;
            8'h61: exp_lut8 = 16'd271;
            8'h62: exp_lut8 = 16'd274;
            8'h63: exp_lut8 = 16'd276;
            8'h64: exp_lut8 = 16'd277;
            8'h65: exp_lut8 = 16'd280;
            8'h66: exp_lut8 = 16'd282;
            8'h67: exp_lut8 = 16'd284;
            8'h68: exp_lut8 = 16'd287;
            8'h69: exp_lut8 = 16'd288;
            8'h6a: exp_lut8 = 16'd290;
            8'h6b: exp_lut8 = 16'd293;
            8'h6c: exp_lut8 = 16'd295;
            8'h6d: exp_lut8 = 16'd297;
            8'h6e: exp_lut8 = 16'd300;
            8'h6f: exp_lut8 = 16'd301;
            8'h70: exp_lut8 = 16'd303;
            8'h71: exp_lut8 = 16'd306;
            8'h72: exp_lut8 = 16'd308;
            8'h73: exp_lut8 = 16'd311;
            8'h74: exp_lut8 = 16'd313;
            8'h75: exp_lut8 = 16'd315;
            8'h76: exp_lut8 = 16'd318;
            8'h77: exp_lut8 = 16'd320;
            8'h78: exp_lut8 = 16'd323;
            8'h79: exp_lut8 = 16'd324;
            8'h7a: exp_lut8 = 16'd327;
            8'h7b: exp_lut8 = 16'd329;
            8'h7c: exp_lut8 = 16'd331;
            8'h7d: exp_lut8 = 16'd334;
            8'h7e: exp_lut8 = 16'd336;
            8'h7f: exp_lut8 = 16'd339;
            8'h80: exp_lut8 = 16'd341;
            8'h81: exp_lut8 = 16'd344;
            8'h82: exp_lut8 = 16'd346;
            8'h83: exp_lut8 = 16'd349;
            8'h84: exp_lut8 = 16'd351;
            8'h85: exp_lut8 = 16'd354;
            8'h86: exp_lut8 = 16'd357;
            8'h87: exp_lut8 = 16'd359;
            8'h88: exp_lut8 = 16'd363;
            8'h89: exp_lut8 = 16'd365;
            8'h8a: exp_lut8 = 16'd368;
            8'h8b: exp_lut8 = 16'd370;
            8'h8c: exp_lut8 = 16'd373;
            8'h8d: exp_lut8 = 16'd376;
            8'h8e: exp_lut8 = 16'd378;
            8'h8f: exp_lut8 = 16'd381;
            8'h90: exp_lut8 = 16'd383;
            8'h91: exp_lut8 = 16'd386;
            8'h92: exp_lut8 = 16'd390;
            8'h93: exp_lut8 = 16'd392;
            8'h94: exp_lut8 = 16'd395;
            8'h95: exp_lut8 = 16'd398;
            8'h96: exp_lut8 = 16'd400;
            8'h97: exp_lut8 = 16'd403;
            8'h98: exp_lut8 = 16'd407;
            8'h99: exp_lut8 = 16'd410;
            8'h9a: exp_lut8 = 16'd412;
            8'h9b: exp_lut8 = 16'd415;
            8'h9c: exp_lut8 = 16'd418;
            8'h9d: exp_lut8 = 16'd421;
            8'h9e: exp_lut8 = 16'd424;
            8'h9f: exp_lut8 = 16'd427;
            8'ha0: exp_lut8 = 16'd430;
            8'ha1: exp_lut8 = 16'd434;
            8'ha2: exp_lut8 = 16'd436;
            8'ha3: exp_lut8 = 16'd439;
            8'ha4: exp_lut8 = 16'd442;
            8'ha5: exp_lut8 = 16'd446;
            8'ha6: exp_lut8 = 16'd449;
            8'ha7: exp_lut8 = 16'd451;
            8'ha8: exp_lut8 = 16'd455;
            8'ha9: exp_lut8 = 16'd458;
            8'haa: exp_lut8 = 16'd461;
            8'hab: exp_lut8 = 16'd464;
            8'hac: exp_lut8 = 16'd468;
            8'had: exp_lut8 = 16'd471;
            8'hae: exp_lut8 = 16'd475;
            8'haf: exp_lut8 = 16'd478;
            8'hb0: exp_lut8 = 16'd481;
            8'hb1: exp_lut8 = 16'd484;
            8'hb2: exp_lut8 = 16'd487;
            8'hb3: exp_lut8 = 16'd490;
            8'hb4: exp_lut8 = 16'd494;
            8'hb5: exp_lut8 = 16'd497;
            8'hb6: exp_lut8 = 16'd501;
            8'hb7: exp_lut8 = 16'd504;
            8'hb8: exp_lut8 = 16'd508;
            8'hb9: exp_lut8 = 16'd511;
            8'hba: exp_lut8 = 16'd515;
            8'hbb: exp_lut8 = 16'd519;
            8'hbc: exp_lut8 = 16'd522;
            8'hbd: exp_lut8 = 16'd526;
            8'hbe: exp_lut8 = 16'd529;
            8'hbf: exp_lut8 = 16'd533;
            8'hc0: exp_lut8 = 16'd536;
            8'hc1: exp_lut8 = 16'd540;
            8'hc2: exp_lut8 = 16'd543;
            8'hc3: exp_lut8 = 16'd548;
            8'hc4: exp_lut8 = 16'd551;
            8'hc5: exp_lut8 = 16'd555;
            8'hc6: exp_lut8 = 16'd558;
            8'hc7: exp_lut8 = 16'd562;
            8'hc8: exp_lut8 = 16'd566;
            8'hc9: exp_lut8 = 16'd570;
            8'hca: exp_lut8 = 16'd574;
            8'hcb: exp_lut8 = 16'd577;
            8'hcc: exp_lut8 = 16'd581;
            8'hcd: exp_lut8 = 16'd585;
            8'hce: exp_lut8 = 16'd589;
            8'hcf: exp_lut8 = 16'd593;
            8'hd0: exp_lut8 = 16'd597;
            8'hd1: exp_lut8 = 16'd601;
            8'hd2: exp_lut8 = 16'd605;
            8'hd3: exp_lut8 = 16'd609;
            8'hd4: exp_lut8 = 16'd613;
            8'hd5: exp_lut8 = 16'd616;
            8'hd6: exp_lut8 = 16'd621;
            8'hd7: exp_lut8 = 16'd625;
            8'hd8: exp_lut8 = 16'd630;
            8'hd9: exp_lut8 = 16'd633;
            8'hda: exp_lut8 = 16'd637;
            8'hdb: exp_lut8 = 16'd642;
            8'hdc: exp_lut8 = 16'd645;
            8'hdd: exp_lut8 = 16'd650;
            8'hde: exp_lut8 = 16'd654;
            8'hdf: exp_lut8 = 16'd659;
            8'he0: exp_lut8 = 16'd662;
            8'he1: exp_lut8 = 16'd667;
            8'he2: exp_lut8 = 16'd672;
            8'he3: exp_lut8 = 16'd676;
            8'he4: exp_lut8 = 16'd680;
            8'he5: exp_lut8 = 16'd684;
            8'he6: exp_lut8 = 16'd689;
            8'he7: exp_lut8 = 16'd693;
            8'he8: exp_lut8 = 16'd698;
            8'he9: exp_lut8 = 16'd702;
            8'hea: exp_lut8 = 16'd706;
            8'heb: exp_lut8 = 16'd711;
            8'hec: exp_lut8 = 16'd716;
            8'hed: exp_lut8 = 16'd721;
            8'hee: exp_lut8 = 16'd725;
            8'hef: exp_lut8 = 16'd729;
            8'hf0: exp_lut8 = 16'd734;
            8'hf1: exp_lut8 = 16'd738;
            8'hf2: exp_lut8 = 16'd743;
            8'hf3: exp_lut8 = 16'd748;
            8'hf4: exp_lut8 = 16'd753;
            8'hf5: exp_lut8 = 16'd758;
            8'hf6: exp_lut8 = 16'd763;
            8'hf7: exp_lut8 = 16'd767;
            8'hf8: exp_lut8 = 16'd772;
            8'hf9: exp_lut8 = 16'd776;
            8'hfa: exp_lut8 = 16'd781;
            8'hfb: exp_lut8 = 16'd786;
            8'hfc: exp_lut8 = 16'd791;
            8'hfd: exp_lut8 = 16'd796;
            8'hfe: exp_lut8 = 16'd801;
            default: exp_lut8 = 16'd806;
          endcase
        end
      endfunction

      always_ff @(posedge clk) begin
        if (rst) begin
          stage1_valid <= 1'b0;
          x_s1         <= 8'h00;
          exp_out      <= '0;
        end else begin
          stage1_valid <= enable;

          if (enable) begin
            x_s1 <= x_in;
          end

          if (stage1_valid) begin
            exp_out <= exp_lut8(x_s1);
          end
        end
      end
    end else begin : gen_generic_poly
      localparam int FRAC = WIDTH - 1;
      localparam int X2W  = 2 * WIDTH;
      localparam int X3W  = 3 * WIDTH;
      localparam logic [2*WIDTH-1:0] ONE_FIXED = {{(2*WIDTH-FRAC-1){1'b0}}, 1'b1, {FRAC{1'b0}}};

      logic               stage1_valid;
      logic               stage2_valid;
      logic [WIDTH-1:0]   x_s1;
      logic [WIDTH+1:0]   x2_scaled_s1;
      logic [WIDTH+2:0]   x3_scaled_s1;
      logic [X2W-1:0]     x2_full;
      logic [X3W-1:0]     x3_full;
      logic [WIDTH+1:0]   x2_scaled_next;
      logic [WIDTH+2:0]   x3_scaled_next;
      logic [2*WIDTH-1:0] sum_stage2;
      logic [2*WIDTH-1:0] x_term_ext;
      logic [2*WIDTH-1:0] x2_term_ext;
      logic [2*WIDTH-1:0] x3_term_ext;

      assign x2_full = x_in * x_in;
      assign x3_full = x2_full * x_in;

      if (FRAC > 0) begin : gen_frac_shift
        assign x2_scaled_next = (x2_full + ({{(X2W-1){1'b0}}, 1'b1} << (FRAC - 1))) >> FRAC;
        assign x3_scaled_next = (x3_full + ({{(X3W-1){1'b0}}, 1'b1} << (2*FRAC - 1))) >> (2*FRAC);
      end else begin : gen_int_shift
        assign x2_scaled_next = x2_full[WIDTH+1:0];
        assign x3_scaled_next = x3_full[WIDTH+2:0];
      end

      assign x_term_ext  = {{WIDTH{1'b0}}, x_s1};
      assign x2_term_ext = {{(WIDTH-2){1'b0}}, ((x2_scaled_s1 + 1'b1) >> 1)};
      assign x3_term_ext = {{(WIDTH-3){1'b0}}, ((x3_scaled_s1 + 3'd3) / 3'd6)};
      assign sum_stage2  = (ONE_FIXED + x_term_ext) + (x2_term_ext + x3_term_ext);

      always_ff @(posedge clk) begin
        if (rst) begin
          stage1_valid <= 1'b0;
          stage2_valid <= 1'b0;
          x_s1         <= '0;
          x2_scaled_s1 <= '0;
          x3_scaled_s1 <= '0;
          exp_out      <= '0;
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
    end
  endgenerate

endmodule
