//! 配布するアーカイブをリンクできるかを確認するプログラム。
//! アーカイブの Rust の実装と Rust の std が同じリンクに入るため、
//! rust_eh_personality のような固定名のシンボルが重複していないかを確認できる。

// edition 2024 では extern ブロックに unsafe が必要になる
unsafe extern "C" {
    // テストの本体。link_test.cc が C の関数として公開している
    fn webrtc_link_test_main() -> i32;
}

fn main() {
    // std の起動処理は内部でパニックを捕まえるため、リンクには必ず std の
    // rust_eh_personality が入る。アーカイブの Rust の実装も同じシンボルを
    // 定義しているので、重複していればリンクに失敗する
    let code = unsafe { webrtc_link_test_main() };
    if code == 0 {
        std::println!("link_test_rust: 成功しました");
    } else {
        std::process::exit(code);
    }
}
