import pytest

from convert_to_mp4.audio import AudioInfo, calculate_optimal_bitrate, should_reencode


class TestCalculateOptimalBitrate:
    def test_ac3_applies_two_thirds_ratio(self):
        # 384 kbps AC3 -> 384 * 2/3 = 256 -> rounds to 256
        assert calculate_optimal_bitrate(384, "ac3", 128, 320) == 256

    def test_eac3_applies_two_thirds_ratio(self):
        # 640 kbps EAC3 -> 640 * 2/3 = 426 -> clamp to 320
        assert calculate_optimal_bitrate(640, "eac3", 128, 320) == 320

    def test_mp3_applies_seven_tenths_ratio(self):
        # 320 kbps MP3 -> 320 * 7/10 = 224 -> rounds to 224
        assert calculate_optimal_bitrate(320, "mp3", 128, 320) == 224

    def test_aac_keeps_same_bitrate(self):
        # 192 kbps AAC -> 192 -> rounds to 192
        assert calculate_optimal_bitrate(192, "aac", 128, 256) == 192

    def test_unknown_codec_applies_three_quarters(self):
        # 256 kbps FLAC -> 256 * 3/4 = 192 -> rounds to 192
        assert calculate_optimal_bitrate(256, "flac", 128, 256) == 192

    def test_clamps_to_min_quality(self):
        # 64 kbps MP3 -> 64 * 7/10 = 44 -> clamp to 128
        assert calculate_optimal_bitrate(64, "mp3", 128, 256) == 128

    def test_clamps_to_max_quality(self):
        # 512 kbps AC3 -> 512 * 2/3 = 341 -> clamp to 256
        assert calculate_optimal_bitrate(512, "ac3", 128, 256) == 256

    def test_rounds_up_to_nearest_standard(self):
        # 200 kbps AAC -> 200 -> nearest standard >= 200 is 224
        assert calculate_optimal_bitrate(200, "aac", 128, 320) == 224

    def test_zero_bitrate_returns_192(self):
        assert calculate_optimal_bitrate(0, "ac3", 128, 256) == 192

    def test_none_bitrate_returns_192(self):
        assert calculate_optimal_bitrate(None, "ac3", 128, 256) == 192

    def test_bitrate_in_bps_converted_to_kbps(self):
        # 192000 bps -> 192 kbps -> AAC -> 192
        assert calculate_optimal_bitrate(192000, "aac", 128, 256) == 192


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
