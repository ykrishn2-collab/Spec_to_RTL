module exp_fixed_point #(
  parameter WIDTH = 8
) (
  input  logic               clk,
  input  logic               rst,
  input  logic               enable,
  input  logic [WIDTH-1:0]   x_in,
  output logic [2*WIDTH-1:0] exp_out
);

  localparam int FRAC_BITS = WIDTH - 1;
  localparam int OUT_W     = 2 * WIDTH;
  localparam logic [OUT_W-1:0] TERM_ONE = {{(OUT_W-(FRAC_BITS+1)){1'b0}}, 1'b1, {FRAC_BITS{1'b0}}};

  logic [WIDTH-1:0] x_s1;
  logic [OUT_W-1:0] approx_s2;
  logic [OUT_W-1:0] approx_s3;
  logic             valid_s1;
  logic             valid_s2;
  logic             valid_s3;

  function automatic logic [15:0] approx_exp_q8(input logic [7:0] x);
    begin
      case (x)
        8'd0: approx_exp_q8 = 16'd128;
        8'd1: approx_exp_q8 = 16'd129;
        8'd2: approx_exp_q8 = 16'd130;
        8'd3: approx_exp_q8 = 16'd131;
        8'd4: approx_exp_q8 = 16'd132;
        8'd5: approx_exp_q8 = 16'd133;
        8'd6: approx_exp_q8 = 16'd134;
        8'd7: approx_exp_q8 = 16'd135;
        8'd8: approx_exp_q8 = 16'd136;
        8'd9: approx_exp_q8 = 16'd137;
        8'd10: approx_exp_q8 = 16'd138;
        8'd11: approx_exp_q8 = 16'd139;
        8'd12: approx_exp_q8 = 16'd140;
        8'd13: approx_exp_q8 = 16'd141;
        8'd14: approx_exp_q8 = 16'd142;
        8'd15: approx_exp_q8 = 16'd143;
        8'd16: approx_exp_q8 = 16'd145;
        8'd17: approx_exp_q8 = 16'd146;
        8'd18: approx_exp_q8 = 16'd147;
        8'd19: approx_exp_q8 = 16'd148;
        8'd20: approx_exp_q8 = 16'd149;
        8'd21: approx_exp_q8 = 16'd150;
        8'd22: approx_exp_q8 = 16'd151;
        8'd23: approx_exp_q8 = 16'd153;
        8'd24: approx_exp_q8 = 16'd154;
        8'd25: approx_exp_q8 = 16'd155;
        8'd26: approx_exp_q8 = 16'd156;
        8'd27: approx_exp_q8 = 16'd157;
        8'd28: approx_exp_q8 = 16'd159;
        8'd29: approx_exp_q8 = 16'd160;
        8'd30: approx_exp_q8 = 16'd161;
        8'd31: approx_exp_q8 = 16'd162;
        8'd32: approx_exp_q8 = 16'd164;
        8'd33: approx_exp_q8 = 16'd165;
        8'd34: approx_exp_q8 = 16'd166;
        8'd35: approx_exp_q8 = 16'd167;
        8'd36: approx_exp_q8 = 16'd169;
        8'd37: approx_exp_q8 = 16'd170;
        8'd38: approx_exp_q8 = 16'd171;
        8'd39: approx_exp_q8 = 16'd172;
        8'd40: approx_exp_q8 = 16'd174;
        8'd41: approx_exp_q8 = 16'd175;
        8'd42: approx_exp_q8 = 16'd176;
        8'd43: approx_exp_q8 = 16'd178;
        8'd44: approx_exp_q8 = 16'd179;
        8'd45: approx_exp_q8 = 16'd180;
        8'd46: approx_exp_q8 = 16'd182;
        8'd47: approx_exp_q8 = 16'd184;
        8'd48: approx_exp_q8 = 16'd186;
        8'd49: approx_exp_q8 = 16'd187;
        8'd50: approx_exp_q8 = 16'd188;
        8'd51: approx_exp_q8 = 16'd190;
        8'd52: approx_exp_q8 = 16'd191;
        8'd53: approx_exp_q8 = 16'd192;
        8'd54: approx_exp_q8 = 16'd194;
        8'd55: approx_exp_q8 = 16'd195;
        8'd56: approx_exp_q8 = 16'd197;
        8'd57: approx_exp_q8 = 16'd198;
        8'd58: approx_exp_q8 = 16'd200;
        8'd59: approx_exp_q8 = 16'd202;
        8'd60: approx_exp_q8 = 16'd204;
        8'd61: approx_exp_q8 = 16'd205;
        8'd62: approx_exp_q8 = 16'd207;
        8'd63: approx_exp_q8 = 16'd208;
        8'd64: approx_exp_q8 = 16'd210;
        8'd65: approx_exp_q8 = 16'd211;
        8'd66: approx_exp_q8 = 16'd213;
        8'd67: approx_exp_q8 = 16'd215;
        8'd68: approx_exp_q8 = 16'd217;
        8'd69: approx_exp_q8 = 16'd218;
        8'd70: approx_exp_q8 = 16'd220;
        8'd71: approx_exp_q8 = 16'd221;
        8'd72: approx_exp_q8 = 16'd223;
        8'd73: approx_exp_q8 = 16'd224;
        8'd74: approx_exp_q8 = 16'd227;
        8'd75: approx_exp_q8 = 16'd228;
        8'd76: approx_exp_q8 = 16'd230;
        8'd77: approx_exp_q8 = 16'd232;
        8'd78: approx_exp_q8 = 16'd233;
        8'd79: approx_exp_q8 = 16'd236;
        8'd80: approx_exp_q8 = 16'd238;
        8'd81: approx_exp_q8 = 16'd239;
        8'd82: approx_exp_q8 = 16'd241;
        8'd83: approx_exp_q8 = 16'd242;
        8'd84: approx_exp_q8 = 16'd245;
        8'd85: approx_exp_q8 = 16'd247;
        8'd86: approx_exp_q8 = 16'd248;
        8'd87: approx_exp_q8 = 16'd250;
        8'd88: approx_exp_q8 = 16'd252;
        8'd89: approx_exp_q8 = 16'd254;
        8'd90: approx_exp_q8 = 16'd256;
        8'd91: approx_exp_q8 = 16'd258;
        8'd92: approx_exp_q8 = 16'd260;
        8'd93: approx_exp_q8 = 16'd262;
        8'd94: approx_exp_q8 = 16'd264;
        8'd95: approx_exp_q8 = 16'd266;
        8'd96: approx_exp_q8 = 16'd269;
        8'd97: approx_exp_q8 = 16'd270;
        8'd98: approx_exp_q8 = 16'd272;
        8'd99: approx_exp_q8 = 16'd274;
        8'd100: approx_exp_q8 = 16'd277;
        8'd101: approx_exp_q8 = 16'd278;
        8'd102: approx_exp_q8 = 16'd280;
        8'd103: approx_exp_q8 = 16'd283;
        8'd104: approx_exp_q8 = 16'd285;
        8'd105: approx_exp_q8 = 16'd287;
        8'd106: approx_exp_q8 = 16'd289;
        8'd107: approx_exp_q8 = 16'd291;
        8'd108: approx_exp_q8 = 16'd293;
        8'd109: approx_exp_q8 = 16'd296;
        8'd110: approx_exp_q8 = 16'd298;
        8'd111: approx_exp_q8 = 16'd300;
        8'd112: approx_exp_q8 = 16'd303;
        8'd113: approx_exp_q8 = 16'd304;
        8'd114: approx_exp_q8 = 16'd307;
        8'd115: approx_exp_q8 = 16'd309;
        8'd116: approx_exp_q8 = 16'd311;
        8'd117: approx_exp_q8 = 16'd314;
        8'd118: approx_exp_q8 = 16'd316;
        8'd119: approx_exp_q8 = 16'd319;
        8'd120: approx_exp_q8 = 16'd321;
        8'd121: approx_exp_q8 = 16'd324;
        8'd122: approx_exp_q8 = 16'd326;
        8'd123: approx_exp_q8 = 16'd328;
        8'd124: approx_exp_q8 = 16'd331;
        8'd125: approx_exp_q8 = 16'd333;
        8'd126: approx_exp_q8 = 16'd336;
        8'd127: approx_exp_q8 = 16'd338;
        8'd128: approx_exp_q8 = 16'd341;
        8'd129: approx_exp_q8 = 16'd343;
        8'd130: approx_exp_q8 = 16'd346;
        8'd131: approx_exp_q8 = 16'd348;
        8'd132: approx_exp_q8 = 16'd351;
        8'd133: approx_exp_q8 = 16'd353;
        8'd134: approx_exp_q8 = 16'd356;
        8'd135: approx_exp_q8 = 16'd359;
        8'd136: approx_exp_q8 = 16'd361;
        8'd137: approx_exp_q8 = 16'd364;
        8'd138: approx_exp_q8 = 16'd366;
        8'd139: approx_exp_q8 = 16'd369;
        8'd140: approx_exp_q8 = 16'd371;
        8'd141: approx_exp_q8 = 16'd374;
        8'd142: approx_exp_q8 = 16'd377;
        8'd143: approx_exp_q8 = 16'd379;
        8'd144: approx_exp_q8 = 16'd383;
        8'd145: approx_exp_q8 = 16'd386;
        8'd146: approx_exp_q8 = 16'd388;
        8'd147: approx_exp_q8 = 16'd391;
        8'd148: approx_exp_q8 = 16'd393;
        8'd149: approx_exp_q8 = 16'd396;
        8'd150: approx_exp_q8 = 16'd399;
        8'd151: approx_exp_q8 = 16'd403;
        8'd152: approx_exp_q8 = 16'd405;
        8'd153: approx_exp_q8 = 16'd408;
        8'd154: approx_exp_q8 = 16'd411;
        8'd155: approx_exp_q8 = 16'd413;
        8'd156: approx_exp_q8 = 16'd417;
        8'd157: approx_exp_q8 = 16'd420;
        8'd158: approx_exp_q8 = 16'd423;
        8'd159: approx_exp_q8 = 16'd425;
        8'd160: approx_exp_q8 = 16'd429;
        8'd161: approx_exp_q8 = 16'd432;
        8'd162: approx_exp_q8 = 16'd435;
        8'd163: approx_exp_q8 = 16'd438;
        8'd164: approx_exp_q8 = 16'd441;
        8'd165: approx_exp_q8 = 16'd444;
        8'd166: approx_exp_q8 = 16'd447;
        8'd167: approx_exp_q8 = 16'd450;
        8'd168: approx_exp_q8 = 16'd454;
        8'd169: approx_exp_q8 = 16'd457;
        8'd170: approx_exp_q8 = 16'd459;
        8'd171: approx_exp_q8 = 16'd463;
        8'd172: approx_exp_q8 = 16'd466;
        8'd173: approx_exp_q8 = 16'd469;
        8'd174: approx_exp_q8 = 16'd473;
        8'd175: approx_exp_q8 = 16'd476;
        8'd176: approx_exp_q8 = 16'd480;
        8'd177: approx_exp_q8 = 16'd483;
        8'd178: approx_exp_q8 = 16'd486;
        8'd179: approx_exp_q8 = 16'd490;
        8'd180: approx_exp_q8 = 16'd493;
        8'd181: approx_exp_q8 = 16'd496;
        8'd182: approx_exp_q8 = 16'd500;
        8'd183: approx_exp_q8 = 16'd503;
        8'd184: approx_exp_q8 = 16'd507;
        8'd185: approx_exp_q8 = 16'd510;
        8'd186: approx_exp_q8 = 16'd514;
        8'd187: approx_exp_q8 = 16'd517;
        8'd188: approx_exp_q8 = 16'd521;
        8'd189: approx_exp_q8 = 16'd524;
        8'd190: approx_exp_q8 = 16'd528;
        8'd191: approx_exp_q8 = 16'd531;
        8'd192: approx_exp_q8 = 16'd536;
        8'd193: approx_exp_q8 = 16'd539;
        8'd194: approx_exp_q8 = 16'd543;
        8'd195: approx_exp_q8 = 16'd546;
        8'd196: approx_exp_q8 = 16'd550;
        8'd197: approx_exp_q8 = 16'd553;
        8'd198: approx_exp_q8 = 16'd557;
        8'd199: approx_exp_q8 = 16'd561;
        8'd200: approx_exp_q8 = 16'd565;
        8'd201: approx_exp_q8 = 16'd568;
        8'd202: approx_exp_q8 = 16'd572;
        8'd203: approx_exp_q8 = 16'd576;
        8'd204: approx_exp_q8 = 16'd580;
        8'd205: approx_exp_q8 = 16'd584;
        8'd206: approx_exp_q8 = 16'd587;
        8'd207: approx_exp_q8 = 16'd592;
        8'd208: approx_exp_q8 = 16'd596;
        8'd209: approx_exp_q8 = 16'd599;
        8'd210: approx_exp_q8 = 16'd604;
        8'd211: approx_exp_q8 = 16'd607;
        8'd212: approx_exp_q8 = 16'd611;
        8'd213: approx_exp_q8 = 16'd616;
        8'd214: approx_exp_q8 = 16'd619;
        8'd215: approx_exp_q8 = 16'd624;
        8'd216: approx_exp_q8 = 16'd628;
        8'd217: approx_exp_q8 = 16'd631;
        8'd218: approx_exp_q8 = 16'd636;
        8'd219: approx_exp_q8 = 16'd640;
        8'd220: approx_exp_q8 = 16'd645;
        8'd221: approx_exp_q8 = 16'd648;
        8'd222: approx_exp_q8 = 16'd653;
        8'd223: approx_exp_q8 = 16'd657;
        8'd224: approx_exp_q8 = 16'd662;
        8'd225: approx_exp_q8 = 16'd665;
        8'd226: approx_exp_q8 = 16'd670;
        8'd227: approx_exp_q8 = 16'd674;
        8'd228: approx_exp_q8 = 16'd679;
        8'd229: approx_exp_q8 = 16'd683;
        8'd230: approx_exp_q8 = 16'd687;
        8'd231: approx_exp_q8 = 16'd692;
        8'd232: approx_exp_q8 = 16'd697;
        8'd233: approx_exp_q8 = 16'd701;
        8'd234: approx_exp_q8 = 16'd705;
        8'd235: approx_exp_q8 = 16'd710;
        8'd236: approx_exp_q8 = 16'd714;
        8'd237: approx_exp_q8 = 16'd719;
        8'd238: approx_exp_q8 = 16'd724;
        8'd239: approx_exp_q8 = 16'd728;
        8'd240: approx_exp_q8 = 16'd733;
        8'd241: approx_exp_q8 = 16'd737;
        8'd242: approx_exp_q8 = 16'd742;
        8'd243: approx_exp_q8 = 16'd746;
        8'd244: approx_exp_q8 = 16'd751;
        8'd245: approx_exp_q8 = 16'd756;
        8'd246: approx_exp_q8 = 16'd761;
        8'd247: approx_exp_q8 = 16'd766;
        8'd248: approx_exp_q8 = 16'd771;
        8'd249: approx_exp_q8 = 16'd776;
        8'd250: approx_exp_q8 = 16'd780;
        8'd251: approx_exp_q8 = 16'd785;
        8'd252: approx_exp_q8 = 16'd790;
        8'd253: approx_exp_q8 = 16'd795;
        8'd254: approx_exp_q8 = 16'd800;
        default: approx_exp_q8 = 16'd805;
      endcase
    end
  endfunction

  function automatic logic [OUT_W-1:0] approx_exp_generic(input logic [WIDTH-1:0] x);
    logic [OUT_W-1:0] x_sq_term;
    logic [OUT_W-1:0] x_cu_term;
    logic [3*WIDTH-1:0] x_cube_full;
    begin
      x_sq_term    = (x * x) >> WIDTH;
      x_cube_full  = (x * x) * x;
      x_cu_term    = (x_cube_full >> (2 * FRAC_BITS)) / 6;
      approx_exp_generic = TERM_ONE + {{(OUT_W-WIDTH){1'b0}}, x} + x_sq_term + x_cu_term;
    end
  endfunction

  always_ff @(posedge clk) begin
    if (rst) begin
      x_s1     <= '0;
      approx_s2 <= '0;
      approx_s3 <= '0;
      valid_s1  <= 1'b0;
      valid_s2  <= 1'b0;
      valid_s3  <= 1'b0;
      exp_out   <= '0;
    end else begin
      if (enable) begin
        x_s1 <= x_in;
      end
      valid_s1 <= enable;

      if (valid_s1) begin
        if (WIDTH == 8) begin
          approx_s2 <= {{(OUT_W-16){1'b0}}, approx_exp_q8(x_s1[7:0])};
        end else begin
          approx_s2 <= approx_exp_generic(x_s1);
        end
      end
      valid_s2 <= valid_s1;

      if (valid_s2) begin
        approx_s3 <= approx_s2;
      end
      valid_s3  <= valid_s2;

      if (valid_s3) begin
        exp_out <= approx_s3;
      end
    end
  end

endmodule
