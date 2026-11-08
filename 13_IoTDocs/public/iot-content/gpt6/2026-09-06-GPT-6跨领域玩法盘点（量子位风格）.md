# GPT-6 Astra：一周造出整座曼哈顿，连杭州都被搬进了网页

> [你的名字] 发自 [你的公众号] | 公众号 [你的ID]

短短一周，GPT-6 Astra 干了一件让一众 3D 工作室头皮发麻的事——它用 Unreal Engine 引擎，把整个曼哈顿一砖一瓦地"施工"了出来。

不是贴图，不是概念片。是能逐条街道推进、让每一处都严丝合缝的数字孪生城市。

而这，只是开胃菜。

▶ 视频演示（来源 X @mattshumer_）：https://x.com/mattshumer_/status/2095609734845927525/video/1
本地备用：assets/video/01_manhattan.mp4

## 曼哈顿，被它一砖一瓦"施工"出来

事情要从 OpenAI 发布 Astra 说起。

短短一周时间里，Astra 通过 Unreal Engine 打造了这个曼哈顿世界。它真的能够逐条街道进行施工，让每一处都变得完美无缺——不是游戏引擎里随手摆的盆景，而是一整套可生长的城市骨架。

你以为这是某个大型团队的半年工期？不，是一个模型，自己干的。

## 房子还没建，你先能逛了

更离谱的在后面。

GPT-6 Astra 在 Blender 里建模了一整栋房子，再把它转成 Unreal Engine 5 里的漫游体验。全程独立完成。

泳池、花园、客厅、厨房，你能以这种方式，在房子真正存在之前就先看到它。换句话说，过去这种可视化服务，需要一家工作室拉着建筑师和 3D 艺术家一起肝；现在，一个提示词搞定。

OpenAI 表示，Astra 已经能像人一样熟练操作 Blender、FreeCAD 和 KiCad：打开程序、建模、导出。在 BenchCAD（CAD 设计考试）里，它考了 **95.9%**——上一个模型，只有 **83.3%**。

▶ 视频演示（来源 X @goofyninjaaa）：https://x.com/goofyninjaaa/status/2095592572286533644/video/1
本地备用：assets/video/03_house_unreal.mp4

## 24 分钟，把整座杭州搬进网页

你以为这就完了？

刚上线的 Astra，直接用 Three.js 把杭州连同周边完整 3D 还原了：西湖、雷峰塔、钱江新城、奥体大莲花、龙井茶山、西溪湿地……甚至延伸到富阳、桐庐、绍兴。

拖动旋转、滚轮缩放、点地标自动飞过去，还能切白天/日落/夜景，开自动漫游随便逛。建筑细节、茶田垄沟、水面小船、桥上车辆全都有——不是静态图，是真正可交互的微缩杭州。

杭州的朋友赶紧认认看，你能认出几个地方？

▶ 视频演示（来源 X @NFT_Chen）：https://x.com/NFT_Chen/status/2096143589151756638/video/1
本地备用：assets/video/05_hangzhou_threejs.mp4

## 334 个部件的特斯拉，2234 个部件的人体

因为你们很喜欢那个会"爆炸"的特斯拉模型——

有开发者用 Astra 做了个 3D 网站，能把特斯拉 Model X 拆成 **334 个模型部件**；紧接着，又把男性解剖结构拆成了 **2234 个模型部件**。

我们正处于一个学习的复兴时期。过去要搞懂一台车怎么造、人体怎么长，得翻图纸翻教材；现在，一个可交互的 3D 拆解网页，比任何教科书都直观。

▶ 视频演示（来源 X @ashebytes）：https://x.com/ashebytes/status/2096221988763173186/video/1
本地备用：assets/video/06_tesla_anatomy.mp4

## 一块飞控 PCB，它自己画了 3 小时

硬核的来了。

有人用 Codex 里的 GPT-6 在 KiCad 里直接操作，完整记录了 FPV 无人机飞控 PCB 的设计全过程：从电路原理图，到 PCB 布局、走线、元器件摆放，全是一个人（模型）一步步画出来的。

画完它自己跑 ERC、DRC，检查问题，再回头改电路和布局。最后交出了 F405 六层飞控板，还导出了 Gerber、钻孔、BOM、贴装坐标和 STEP 文件——能直接打开看整块板子的 3D 效果。

整个设计过程：**总耗时 3 小时 13 分 56 秒，总 token 消耗约 51,900,896 个（约 5200 万）**，思考强度为高。目前还没打样，实际稳不稳得上板才知道，但从"描述需求"到"画出整块 PCB"，这活儿已经挺让人惊叹了。

▶ 视频演示（来源 X @GoGoFly23）：https://x.com/GoGoFly23/status/2096436525110309251/video/1
本地备用：assets/video/04_pcb_kicad.mp4

## 和 GPT-5.6 同框，差距肉眼可见

光听我吹没用，有对比才有伤害。

Astra 和 GPT-5.6 的对比动画已经出来了。同一个任务，两代模型的完成度、细节密度、容错能力，摆在一起，差距不是一点半点。

▶ 视频演示（来源 X @flowith）：https://x.com/flowith/status/2095750768204877858/video/1
本地备用：assets/video/02_compare.mp4

## 一个人，干了一整个工作室的活

随便一句话 Prompt，等 40 分钟，出来个这种级别的东西——

▶ 视频演示（来源 X @zhengli）：https://x.com/zhengli/status/2096048421543272893/video/1
本地备用：assets/video/07_prompt_40min.mp4

GPT-6 Astra 是新一代的先进 AI 代理软件，在代理式 CAD 领域处于领先地位。人工智能在机械设计领域的能力，确实发生了真正的飞跃。

▶ 视频演示（来源 X @adamdotnew）：https://x.com/adamdotnew/status/2096053889141489669/video/1
本地备用：assets/video/08_agentic_cad.mp4

更妙的是，开源社区已经跟上：text-to-cad v0.5 正好赶在 Astra 发布前推出，能生成 STEP、STL、GLB、3MF、DXF，附带相关代码，作为代理技能库本地运行，完全开源且免费。机械师们，玩得开心。

▶ 视频演示（来源 X @earthtojake）：https://x.com/earthtojake/status/2096020381547008327/video/1
本地备用：assets/video/09_text2cad.mp4

## One More Thing

你会把设计房子的任务，交给建筑师——还是让 ChatGPT 来做？

这个问题，一年前还像个玩笑。现在，看着曼哈顿、杭州、334 个部件的特斯拉和那块自己画完的飞控板，笑不出来了。

Astra 把"世界建模"这件曾经昂贵的事，压到了一个提示词的重量。至于它会不会抢谁的饭碗，数据已经先替它发了言：BenchCAD 95.9% 对 83.3%，3 小时 13 分画完一块六层板。

那就，让子弹再飞一会儿吧。

---

**参考链接（视频均来自 X / OpenAI 发布周）**

- [01 曼哈顿 Unreal 世界 @mattshumer_](https://x.com/mattshumer_/status/2095609734845927525/video/1)
- [02 GPT-6 vs GPT-5.6 对比 @flowith](https://x.com/flowith/status/2095750768204877858/video/1)
- [03 Blender 房子→Unreal 漫游 @goofyninjaaa](https://x.com/goofyninjaaa/status/2095592572286533644/video/1)
- [04 KiCad 飞控 PCB @GoGoFly23](https://x.com/GoGoFly23/status/2096436525110309251/video/1)
- [05 杭州 Three.js @NFT_Chen](https://x.com/NFT_Chen/status/2096143589151756638/video/1)
- [06 特斯拉/人体拆解 @ashebytes](https://x.com/ashebytes/status/2096221988763173186/video/1)
- [07 40 分钟 Prompt 大片 @zhengli](https://x.com/zhengli/status/2096048421543272893/video/1)
- [08 代理式 CAD @adamdotnew](https://x.com/adamdotnew/status/2096053889141489669/video/1)
- [09 text-to-cad v0.5 @earthtojake](https://x.com/earthtojake/status/2096020381547008327/video/1)
