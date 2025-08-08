from datetime import timedelta
import re
import pysrt
import tkinter as tk


def move_down(listbox):
    current_selection = listbox.curselection()
    if current_selection:
        next_index = current_selection[-1] + 1
        if next_index < listbox.size():
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(next_index)
            listbox.activate(next_index)
            listbox.see(next_index)


def move_up(listbox):
    current_selection = listbox.curselection()
    if current_selection:
        previous_index = current_selection[0] - 1
        if previous_index >= 0:
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(previous_index)
            listbox.activate(previous_index)
            listbox.see(previous_index)


def set_cursor_to_center(textbox):
    lines = textbox.get("1.0", tk.END).strip().split("\n")
    center_line_index = len(lines) // 2
    center_char_index = len(lines[center_line_index]) // 2
    textbox.mark_set("insert", f"{center_line_index + 1}.{center_char_index}")
    textbox.see("insert")


def get_milliseconds(srt_time):
    return (
        srt_time.hours * 3600 + srt_time.minutes * 60 + srt_time.seconds
    ) * 1000 + srt_time.milliseconds


def format_time(t: pysrt.srttime.SubRipTime):
    return f'{t.minutes:02}:{t.seconds:02}:{t.milliseconds:03}'


def format_millis(ms):
    seconds = (ms // 1000) % 60
    minutes = (ms // (60 * 1000)) % 60
    milliseconds = ms % 1000
    return f"{minutes:02}:{seconds:02}.{milliseconds:03}"


def avg(arr):
    if not arr:
        return 0
    return sum(arr) / len(arr)


def edit_distance(s1, s2):
    m = len(s1)
    n = len(s2)
    dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0:
                dp[i][j] = j
            elif j == 0:
                dp[i][j] = i
            elif s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i][j - 1],  # insert
                                   dp[i - 1][j],  # delete
                                   dp[i - 1][j - 1])  # replace
    return dp[m][n]


def remove_strange_char(s):
    for c in '`_,\'\"|=()<>[]{}?/\\:;+-~!@#$%^&*1234567890':
        s = s.replace(c, '')
    return s


def remove_chars(s, chars):
    for c in chars:
        s = s.replace(c, '')
    return s


def postprocessing(s):
    if s in ['.', '..']:
        return ''
    if '客服專線' in s:
        return ''
    s = s.replace('親下', '親一下')
    s = s.replace('等下', '等一下')
    s = s.replace('看下', '看一下')
    s = re.sub(r'(?<!\.)\.\.(?!\.)', '...', s)
    s = re.sub(r'(?<!\.)\.(?!\.)', '...', s)
    return s


def str_to_timedelta(s):
    hours, minutes, seconds = map(float, s.split(':'))
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


class SubtitleMaker:
    MIN_SENTENCE_TIME = 100

    def __init__(self):
        self.subtitles = []
        self.last_text = ''
        self.last_confidence = 0
        self.start_time = None

    def next_frame(self, frame_time, text, confidence):
        text = postprocessing(text)
        if not text:
            if self.last_text and self._elapsed(frame_time) >= self.MIN_SENTENCE_TIME:
                self.subtitles.append(pysrt.SubRipItem(
                    index=len(self.subtitles) + 1,
                    start=self._to_srttime(self.start_time),
                    end=self._to_srttime(frame_time),
                    text=self.last_text))
            self.start_time = None
            self.last_text = ''
            self.last_confidence = 0
        elif self._is_similar(text, self.last_text):
            if self._base_text(text) == self._base_text(self.last_text):
                self.last_confidence = max(self.last_confidence, confidence)
                if len(text) > len(self.last_text):
                    self.last_text = text
            elif confidence > self.last_confidence:
                self.last_text = text
                self.last_confidence = confidence
        else:
            if self.last_text and self._elapsed(frame_time) >= self.MIN_SENTENCE_TIME:
                self.subtitles.append(pysrt.SubRipItem(
                    index=len(self.subtitles) + 1,
                    start=self._to_srttime(self.start_time),
                    end=self._to_srttime(frame_time),
                    text=self.last_text))
            self.start_time = frame_time
            self.last_text = text
            self.last_confidence = confidence

    def end(self, end_time):
        if self.last_text and self._elapsed(end_time) >= self.MIN_SENTENCE_TIME:
            self.subtitles.append(pysrt.SubRipItem(
                index=len(self.subtitles) + 1,
                start=self._to_srttime(self.start_time),
                end=self._to_srttime(end_time),
                text=self.last_text))

    def get_subtitles(self):
        return self.subtitles

    def _to_srttime(self, td: timedelta):
        total_ms = int(td.total_seconds() * 1000)
        hours = total_ms // 3600000
        minutes = (total_ms % 3600000) // 60000
        seconds = (total_ms % 60000) // 1000
        milliseconds = total_ms % 1000
        return pysrt.SubRipTime(hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds)

    def _elapsed(self, now: timedelta):
        return (now - self.start_time).total_seconds() * 1000 if self.start_time else 0

    def _base_text(self, t):
        return remove_chars(t, ' 一').replace('...', '')

    def _is_similar(self, a, b):
        if not a or not b:
            return False
        a_clean = remove_chars(a, '. ')
        b_clean = remove_chars(b, '. ')
        dist = edit_distance(a_clean, b_clean)
        if len(a) <= 2:
            return a_clean == b_clean
        elif len(a) <= 6:
            return dist <= 1
        else:
            return dist <= 2
