#!/usr/bin/env python
"""ワーカー起動用のCLIラッパー: デフォルト引数を設定してworker_mainを呼び出す。

ポイント:
- デフォルト引数はこのファイルの _DEFAULT_ARGS にまとめる
- 追加のカスタム引数として `--r_key_event=/dev/input/event17` 形式を受け付ける
  - これは worker 内部で使う R キー検出デバイスを指定するための引数
  - 実装上は環境変数 R_KEY_EVENT に変換してから worker_main を呼び出す
"""

import os
import sys

# デフォルト引数を設定
_DEFAULT_ARGS = [
    "--policy.path=masato-ka/smolvla-donuts-shop-v1",
    "--policy.device=cuda",
    "--robot.type=bi_so101_follower",
    "--robot.id=bi_robot",
    "--robot.left_arm_port=/dev/ttyACM1",
    "--robot.right_arm_port=/dev/ttyACM2",
    "--robot.cameras={front: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30}, back: {type: opencv, index_or_path: /dev/video6, width: 640, height: 480, fps: 30}}",
    "--rtc.enabled=true",
    "--rtc.execution_horizon=12",
    "--rtc.max_guidance_weight=10.0",
    "--duration=120",
    "--fps=30",
    "--use_torch_compile=false",
    '--policy.input_features={"observation.state": {"type": "STATE", "shape": [12]}}',
    '--policy.output_features={"action": {"type": "ACTION", "shape": [12]}}',
    # Rキー検出デバイスのデフォルト (必要に応じて変更)
    # カスタム引数として扱うので、後で worker_cli 内で処理してから main_cli に渡す
    "--r_key_event=/dev/input/event17",
]


def _extract_r_key_event_arg(args: list[str]) -> tuple[list[str], str | None]:
    """引数リストから `--r_key_event` を取り出し、残りの引数と値を返す。

    サポート形式:
    - --r_key_event=/dev/input/event17
    - --r_key_event /dev/input/event17
    """
    filtered: list[str] = []
    r_key_event: str | None = None

    it = iter(range(len(args)))
    i: int
    for i in it:
        arg = args[i]
        if arg.startswith("--r_key_event="):
            # --r_key_event=/path 形式
            r_key_event = arg.split("=", 1)[1]
        elif arg == "--r_key_event":
            # --r_key_event /path 形式
            # 次の要素があればそれを値として消費する
            if i + 1 < len(args):
                r_key_event = args[i + 1]
                next(it, None)  # 次のインデックスをスキップ
        else:
            filtered.append(arg)

    return filtered, r_key_event


def main():
    """メインエントリポイント: デフォルト引数を使用してworker_mainを呼び出す。"""
    # コマンドライン引数があればそれを使用、なければデフォルトを使用
    if len(sys.argv) > 1:
        # ユーザーが引数を指定した場合はそれを使用
        raw_args = sys.argv[1:]
    else:
        # デフォルト引数を使用（sys.argv[0]はスクリプト名なので、それに続けて追加）
        raw_args = _DEFAULT_ARGS

    # カスタム引数 --r_key_event を取り出して環境変数に変換
    args, r_key_event = _extract_r_key_event_arg(raw_args)
    if r_key_event:
        # worker 側では R_KEY_EVENT 環境変数を見てデバイスを選択する
        os.environ["R_KEY_EVENT"] = r_key_event

    # draccus/parser に渡す引数を sys.argv に反映
    sys.argv = [sys.argv[0]] + args

    # worker_mainをインポートして実行
    from robot_controller.worker_main import main_cli

    main_cli()


if __name__ == "__main__":
    main()
