# Git 团队协作操作说明

## 1. 当前状态

仓库位置：`S:\Ti60F225_DemoBoard_v4`，主分支：`main`，GitHub：<https://github.com/Eutopia-n/ours_blt>。

本地 Git 已配置 `origin` 指向上述 GitHub 仓库。新成员可直接克隆；每位开发者仍应在自己的克隆中配置提交姓名和邮箱。

本地仓库负责记录版本；团队共享还需要 GitHub、Gitee 或 GitLab 等平台的远程仓库。各成员使用各自电脑上的克隆，不要共同操作同一份共享磁盘工作目录。

## 2. 设置提交身份

在 PowerShell 中执行。先把下面的姓名和邮箱替换为你自己的信息，不能原样使用占位文本。邮箱可以使用托管平台提供的隐私邮箱。

```powershell
Set-Location 'S:\Ti60F225_DemoBoard_v4'
git config --local user.name '你的姓名或昵称'
git config --local user.email '你的邮箱'
git status --short
```

身份只设置在本仓库，不影响其他项目。修改文件后先查看差异，只暂存本次相关文件，再提交。

## 3. 克隆与同步 GitHub 仓库

```powershell
git clone https://github.com/Eutopia-n/ours_blt.git Ti60F225_DemoBoard_v4
Set-Location Ti60F225_DemoBoard_v4
git remote -v
```

已有克隆先同步主分支：

```powershell
git switch main
git pull --ff-only origin main
```

由负责人邀请成员，并在平台支持时设置 `main` 分支保护，要求通过 Pull Request / Merge Request 审查后合并。

## 4. 每位成员日常开发

新成员在自己的工作目录克隆，并在仓库内配置自己的提交身份：

```powershell
git clone '实际远程仓库地址' Ti60F225_DemoBoard_v4
Set-Location Ti60F225_DemoBoard_v4
git config --local user.name '你的姓名或昵称'
git config --local user.email '你的邮箱'
```

开始一项新功能前，先确保工作区没有未保存到 Git 的修改，再同步主分支、创建个人功能分支：

```powershell
git status
git switch main
git pull --ff-only origin main
git switch -c feature/zhang-uart-rx
```

开发完成后，只暂存本次相关文件。把下面文件路径和提交说明替换为实际内容：

```powershell
git diff
git add -- '本次修改的文件路径'
git diff --cached --stat
git commit -m "feat: 完成UART接收模块并通过仿真"
git push -u origin feature/zhang-uart-rx
```

随后在平台创建合并请求，由另一位成员检查后合并到 `main`。每项新任务使用不同分支名；提交说明只能写实际完成的验证，不要把未验证的结果写成通过。

## 5. FPGA 工程协作约定

1. 一次提交只完成一项明确修改，说明修改原因和验证结果。
2. 修改引脚时，同时提交相关 `*.peri.xml`；修改时序时，同时提交相关 `*.sdc`。
3. 添加 RTL 文件时，同时提交引用该文件的工程 XML，尽量使用相对路径。
4. 同一工程的引脚配置、工程 XML 和 IP 配置尽量由一人集中修改，减少冲突。
5. `.gitignore` 只排除生成物；不能把 IP、ROM 初始化数据或仿真输入误当成缓存删除。
6. 合并 HDL 冲突后重新仿真/编译；硬件相关修改还应重新确认上板现象。
7. 编译产物不进入日常源码提交。需要分享已验证的下载文件时，另行发布，并标注对应提交号、工程及工具版本。

## 6. 常见问题

- `Author identity unknown`：执行第 2 节的两条 `git config --local` 命令。
- 新文件没有出现在 `git status`：执行 `git check-ignore -v -- '具体文件路径'`，定位是哪条规则忽略了它。
- `src refspec main does not match any`：检查是否已创建首次提交，执行 `git log -1`。
- 推送认证失败：检查远程地址和账号权限，并按托管平台要求登录。
- `git pull --ff-only` 失败：本地和远程历史可能发生分叉，先执行 `git status` 与 `git log --oneline --graph --all -15` 查看，不要直接强制推送。

不要使用 `git reset --hard` 或 `git clean -fdx` 作为日常清理手段，后者会删除忽略规则中的本地资料和生成物。
