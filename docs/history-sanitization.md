# 清理 git 历史中的敏感信息

`scripts/audit_history.py` 扫描的是**历史对象**，不是当前工作树。这意味着：在新提交里把
文件改干净，并不会让旧提交变干净——旧的 blob 和旧的提交元数据仍然留在仓库里，GitHub 上
也仍然可以通过 commit SHA 直接访问。

真正清除只能重写历史。本文记录一套已经在镜像克隆上验证过的流程。

## 先审计

```bash
# 把姓名、公司、花名等关键词写进未跟踪的 .audit-patterns（每行一个正则）
uv run python scripts/audit_history.py --patterns-file .audit-patterns
```

输出分三类：

- `custom-pattern` / `home-directory` / `api-key` / `opaque-secret`：某个历史 blob 的内容命中。
- `commit-custom-pattern`：提交的作者、提交者或标题命中。
- 顶部的“提交身份清单”：历史上出现过的所有 author/committer，需要人工确认哪些可以公开。

## 重写

重写会改变所有 commit SHA，需要向所有分支强制推送。开始前先确认：没有未合并的 PR，
其他协作者的本地克隆需要重新克隆或 `git reset --hard`。

1. 安装工具并做一份镜像克隆（**不要**在日常工作副本上操作）：

 ```bash
 uv tool install git-filter-repo
 git clone --mirror https://github.com/<owner>/<repo> repo-mirror
 cd repo-mirror
 ```

2. 删除 GitHub 的只读 PR ref，否则它们会被一起重写却推不回去：

 ```bash
 git for-each-ref --format='delete %(refname)' refs/pull | git update-ref --stdin
 ```

3. 准备两个文件。`replacements.txt` 处理文件内容与提交信息，越具体的规则放越前面：

 ```text
 literal:C:\Users\<你的用户名>\AppData\Local\uv\cache==>%LOCALAPPDATA%\uv\cache
 literal:C:/Users/<你的用户名>/.codex/==>~/.codex/
 literal:<你的公司邮箱>==>><owner>@users.noreply.github.com
 literal:<你的用户名>==>redacted-user
 ```

 `mailmap.txt` 处理作者/提交者身份，格式是 `新身份 <新邮箱> 旧身份 <旧邮箱>`：

 ```text
 <owner> <<owner>@users.noreply.github.com> <旧名字> <<旧邮箱>>
 ```

4. 执行重写：

 ```bash
 git filter-repo --replace-text replacements.txt \
   --replace-message replacements.txt \
   --mailmap mailmap.txt
 ```

5. 在重写后的镜像上复验，应当输出 `OK` 且退出码为 `0`：

 ```bash
 uv run python /path/to/checkout/scripts/audit_history.py \
   --repo . --patterns-file /path/to/.audit-patterns
 ```

6. 复验通过后再强制推送所有分支和标签：

 ```bash
 git push --force --mirror https://github.com/<owner>/<repo>
 ```

## 推送之后

- 旧的提交对象在 GitHub 上仍可能通过 SHA 访问一段时间。要彻底移除缓存对象，需要联系
 GitHub Support 请求 GC。
- 已合并 PR 的页面会显示提交不再属于任何分支，这是重写历史的预期副作用。
- 如果泄漏过真实 API Key，重写历史**不能**代替吊销：先在服务商侧作废旧 Key。
- 之后由 `tests/test_no_sensitive_content.py` 在每次 `uv run pytest` 时守住工作树，
 防止同类内容再次进入历史。
