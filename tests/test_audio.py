from convert_to_mp4.audio import AudioInfo, calculate_optimal_bitrate, should_reencode


class TestCalculateOptimalBitrate:
    def test_ac3_applies_two_thirds_ratio(self):
        assert calculate_optimal_bitrate(384, "ac3", 128, 320) == 256

    def test_eac3_applies_two_thirds_ratio(self):
        assert calculate_optimal_bitrate(640, "eac3", 128, 320) == 320

    def test_mp3_applies_seven_tenths_ratio(self):
        assert calculate_optimal_bitrate(320, "mp3", 128, 320) == 224

    def test_aac_keeps_same_bitrate(self):
        assert calculate_optimal_bitrate(192, "aac", 128, 256) == 192

    def test_unknown_codec_applies_three_quarters(self):
        assert calculate_optimal_bitrate(256, "flac", 128, 256) == 192

    def test_clamps_to_min_quality(self):
        assert calculate_optimal_bitrate(64, "mp3", 128, 256) == 128

    def test_clamps_to_max_quality(self):
        assert calculate_optimal_bitrate(512, "ac3", 128, 256) == 256

    def test_rounds_up_to_nearest_standard(self):
        assert calculate_optimal_bitrate(200, "aac", 128, 320) == 224

    def test_zero_bitrate_returns_192(self):
        assert calculate_optimal_bitrate(0, "ac3", 128, 256) == 192

    def test_none_bitrate_returns_192(self):
        assert calculate_optimal_bitrate(None, "ac3", 128, 256) == 192

    def test_bitrate_in_bps_converted_to_kbps(self):
        assert calculate_optimal_bitrate(192000, "aac", 128, 256) == 192

    def test_high_kbps_not_mistaken_for_bps(self):
        assert calculate_optimal_bitrate(1001, "aac", 128, 320) == 320


class TestShouldReencode:
    def test_aac_stereo_no_force_returns_false(self):
        info = AudioInfo(codec="aac", channels=2, bitrate=192)
        assert should_reencode(info, force_audio=False) is False

    def test_non_aac_returns_true(self):
        info = AudioInfo(codec="ac3", channels=2, bitrate=384)
        assert should_reencode(info, force_audio=False) is True

    def test_more_than_two_channels_returns_true(self):
        info = AudioInfo(codec="aac", channels=6, bitrate=384)
        assert should_reencode(info, force_audio=False) is True

    def test_force_audio_returns_true(self):
        info = AudioInfo(codec="aac", channels=2, bitrate=192)
        assert should_reencode(info, force_audio=True) is True

    def test_mono_aac_no_force_returns_false(self):
        info = AudioInfo(codec="aac", channels=1, bitrate=128)
        assert should_reencode(info, force_audio=False) is False
