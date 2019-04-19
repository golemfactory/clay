from typing import Any, Dict, Tuple

from tests.apps.ffmpeg.task.ffprobe_report import Diff


class FfprobeReportSet:
    def __init__(self):
        self._report_tables = {}

    @classmethod
    def _table_insert(cls,
                      table: Dict[str, Dict[str, Dict[str, Any]]],
                      coordinates: Tuple[str, str, str],
                      value: Any) -> None:

        if coordinates[0] not in table:
            table[coordinates[0]] = {}

        if coordinates[1] not in table[coordinates[0]]:
            table[coordinates[0]][coordinates[1]] = {}

        table[coordinates[0]][coordinates[1]][coordinates[2]] = value

    @classmethod
    def _describe_ffprobe_report_diff(cls, diff: Diff) -> str:
        output_lines = []

        stream_mismatch_found = False
        stream_types_different = False
        for diff_dict in diff:
            if diff_dict['reason'] == "Different attribute values":
                line = "`{}.{}`: `{}` -> `{}`".format(
                    diff_dict['location'],
                    diff_dict['attribute'],
                    diff_dict['modified_value'],
                    diff_dict['original_value'],
                )

                if (diff_dict['location'] == 'format' and
                        diff_dict['attribute'] == 'stream_types'):
                    stream_types_different = True

            elif diff_dict['reason'] == "No matching stream":
                # We can skip this one because the difference will show up
                # in the stream_types dict anyway if the diff is consistent.
                stream_mismatch_found = True
                continue
            else:
                assert False, "Unrecognized 'reason'; add it above"

            output_lines.append(line)

        assert stream_types_different == stream_mismatch_found, \
            "Inconsistent diff. " \
            "stream_types must differ too if there are mismatched streams."

        if len(output_lines) == 0:  # pylint: disable=len-as-condition
            return "OK"

        return "<ol><li>" + "</li><li>".join(output_lines) + "</li><ol>"

    def collect_error(self,
                      error_message: str,
                      experiment_name: str,
                      video_file: str,
                      input_value: str):
        self._table_insert(
            self._report_tables,
            (experiment_name, video_file, input_value),
            error_message,
        )

    def collect_reports(self,
                        diff: Diff,
                        experiment_name: str,
                        video_file: str,
                        input_value: str):
        self._table_insert(
            self._report_tables,
            (experiment_name, video_file, input_value),
            self._describe_ffprobe_report_diff(diff),
        )

    @classmethod
    def _format_markdown_header_line(cls, num_columns):
        return "|-" + "-|-".join('-' * 50 for _ in range(num_columns)) + "-|\n"

    @classmethod
    def _format_markdown_row(cls, column_values):
        return "| " + " | ".join(f"{c:50}" for c in column_values) + " |\n"

    def to_markdown(self):
        output = ""

        for experiment_name in self._report_tables:
            output += f"### {experiment_name}\n\n"

            table = self._report_tables[experiment_name]
            input_columns = sorted({
                input_value
                for video_file in table
                for input_value in table[video_file]
            })

            column_headers = ["Video file"] + [f"`{c}`" for c in input_columns]
            output += self._format_markdown_row(column_headers)
            output += self._format_markdown_header_line(len(input_columns) + 1)

            for video_file in table:
                output += self._format_markdown_row(
                    [video_file] + [
                        table[video_file].get(input_value, "")
                        for input_value in input_columns
                    ]
                )

            output += f"\n"

        return output
