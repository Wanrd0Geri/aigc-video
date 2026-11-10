# 检查命令模板与参数取舍

成文后要跑检查时，按任务读对应小节及「参数取舍」。

## 新稿成文

最终正文检查常用命令：`python3 -X utf8 $HOME/Documents/Codex/aigc-video/scripts/check_prompt.py --prompt "<最终正文.txt>" --task 生成 --labels "<本次素材，逗号分隔>" --report "<本机报告.json>"`

## 改现有提示词

常用命令：`python3 -X utf8 $HOME/Documents/Codex/aigc-video/scripts/check_prompt.py --prompt "<完整新稿.txt>" --task 生成 --baseline "<完整父稿.txt>" --asks asks.txt --lock "<用户锁定的原文>" --adjudicated adjudicated.txt --report "<本机报告.json>"`

## 操作命令（延长 / 编辑 / 衔接）

延长常用命令：`python3 -X utf8 $HOME/Documents/Codex/aigc-video/scripts/check_prompt.py --prompt "<完整操作稿.txt>" --task 延长 --labels "视频1" --report "<本机报告.json>"`

## 白模与运镜参考

全量白模且白模拥有全片时长时常用命令：`python3 -X utf8 $HOME/Documents/Codex/aigc-video/scripts/check_prompt.py --prompt "<完整稿.txt>" --task 生成 --labels "<本次素材，逗号分隔>" --mode 白模 --untimed --shot-seconds "<交接卡每镜秒数，逗号分隔>" --report "<本机报告.json>"`

## 参数取舍

参数含义见 --help，常规任务不必跑 help。以上是带占位符的命令模板：先填入真实路径和事实，Windows把python3换成py -3。--labels按全部实际素材填写，无素材省略；--task按最终命令选一个值，改操作稿仍用编辑/延长/衔接。--lock后传要逐字保留的原文，可重复给多条，不传布尔值或文件名，无逐字锁则省略；--asks第二版起更新后使用；项目的 avoid.txt 记用户明确要求停用的写法，每行「写法 # 原因」，收到这类要求时记入该文件；与 asks.txt 或 adjudicated.txt 放在同目录，检查器会自动读取，也可用 --avoid 显式指定；--adjudicated只传实际已逐条裁定的文件，没有则省略，不为消警告造文件。--baseline取完整真实父稿；--unchanged传未改镜号，逗号分隔（如 1,3），按revise-rules第10节使用；多轮改稿需核对累计增长时带--origin，传本轮开始时固定的起点完整稿路径，asks.txt里的起点注释仍需通过此参数显式传入；局部稿/整镜重写等仅按已有授权和适用条件加参数。白模--untimed/--shot-seconds从卡的条件与真实交接卡取值；衔接按operations要求用无时码与实际每镜秒数。报告对应最终交付正文，沿用本机报告目录；严格审触发与流程不变。
