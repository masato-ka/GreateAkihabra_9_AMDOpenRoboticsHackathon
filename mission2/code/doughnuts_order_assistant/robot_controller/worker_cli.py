#!/usr/bin/env python
"""ワーカー起動用のCLIラッパー: デフォルト引数を設定してworker_mainを呼び出す。"""

import sys

# デフォルト引数を設定
_DEFAULT_ARGS = [
    "--policy.path=masato-ka/smolvla-donuts-shop-v1",
    "--policy.device=cuda",
    "--robot.type=bi_so101_follower",
    "--robot.id=bi_robot",
    "--robot.left_arm_port=/dev/ttyACM3",
    "--robot.right_arm_port=/dev/ttyACM2",
    "--robot.cameras={front: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30}, back: {type: opencv, index_or_path: /dev/video6, width: 640, height: 480, fps: 30}}",
    "--rtc.enabled=true",
    "--rtc.execution_horizon=12",
    "--rtc.max_guidance_weight=10.0",
    "--duration=60",
    "--fps=30",
    "--use_torch_compile=false",
    '--policy.input_features={"observation.state": {"type": "STATE", "shape": [12]}}',
    '--policy.output_features={"action": {"type": "ACTION", "shape": [12]}}',
]


def main():
    """メインエントリポイント: デフォルト引数を使用してworker_mainを呼び出す。"""
    # コマンドライン引数があればそれを使用、なければデフォルトを使用
    if len(sys.argv) > 1:
        # ユーザーが引数を指定した場合はそれを使用
        args = sys.argv[1:]
    else:
        # デフォルト引数を使用（sys.argv[0]はスクリプト名なので、それに続けて追加）
        args = _DEFAULT_ARGS
        sys.argv = [sys.argv[0]] + args

    # worker_mainをインポートして実行
    from robot_controller.worker_main import main_cli

    main_cli()


if __name__ == "__main__":
    main()
