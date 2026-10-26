import vendor.__bootstrap__  # From VNMA.

import gram
import sub_parser


def main() -> None:
    print("=== Isolated Nested Gram Test ===")
    print("[1] Direct Gram import in main_project:")
    print(f"    gram module: {gram.__name__}")
    print(f"    gram path:   {getattr(gram, '__file__', 'unknown')}")

    print("\n[2] Intermediate sub_parser calling Gram:")
    result = sub_parser.analyze_with_gram("int x = 42;")
    print(f"    sub_parser result: {result}")

    assert gram is not None, "Direct gram import failed"
    assert result["status"] == "success", "sub_parser calling gram failed"
    print("\n[SUCCESS] Both nested levels imported and used Gram seamlessly!")


if __name__ == "__main__":
    main()
