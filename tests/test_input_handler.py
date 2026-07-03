from shortform.input_handler import classify_input

def test_classify_url():
    assert classify_input("https://example.com/article/123") == "url"

def test_classify_url_no_scheme_but_domain_like():
    assert classify_input("www.example.com/page") == "url"

def test_classify_topic():
    assert classify_input("고양이 건강 관리 꿀팁") == "topic"
