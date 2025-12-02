import streamlit as st

st.title("シンプルテストアプリ")
st.write("Hello World!")
st.write("もしこのメッセージが表示されれば、Streamlitは正常に動作しています。")

if st.button("テストボタン"):
    st.success("ボタンが正常に機能しました！")