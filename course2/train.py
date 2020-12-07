import os
import cv2
import parl
import numpy as np
import flappy_bird.wrapped_flappy_bird as flappyBird
from parl.utils import logger
from model import Model
from agent import Agent
from replay_memory import ReplayMemory

LEARN_FREQ = 5  # 更新参数步数
MEMORY_SIZE = 20000  # 内存记忆
MEMORY_WARMUP_SIZE = 200  # 热身大小
BATCH_SIZE = 32  # batch大小
LEARNING_RATE = 0.0005  # 学习率大小
GAMMA = 0.99  # 奖励系数
E_GREED = 0.1  # 探索初始概率
E_GREED_DECREMENT = 1e-6  # 在训练过程中，降低探索的概率
MAX_EPISODE = 10000  # 训练次数
RESIZE_SHAPE = (1, 224, 224)  # 训练缩放的大小，减少模型计算，原大小（288, 512）
SAVE_MODEL_PATH = "models/model.ckpt"  # 保存模型路径


# 图像预处理
def preprocess(observation):
    # 裁剪图像
    observation = observation[:observation.shape[0]-100, :]
    # 缩放图像
    observation = cv2.resize(observation, (RESIZE_SHAPE[1], RESIZE_SHAPE[2]))
    # 把图像转成灰度图
    observation = cv2.cvtColor(observation, cv2.COLOR_BGR2GRAY)
    # 图像转换成非黑即白的图像
    ret, observation = cv2.threshold(observation, 1, 255, cv2.THRESH_BINARY)
    # 显示处理过的图像
    cv2.imshow("preprocess", observation)
    cv2.waitKey(1)
    observation = np.expand_dims(observation, axis=0)
    observation = observation / 255.0
    return observation


# 训练模型
def run_train(agent, env, rpm):
    total_reward = 0
    obs = env.reset()
    obs = preprocess(obs)
    step = 0
    while True:
        step += 1
        # 获取随机动作和执行游戏
        action = agent.sample(obs, env)
        next_obs, reward, isOver, info = env.step(action, is_train=True)
        next_obs = preprocess(next_obs)

        # 记录数据
        rpm.append((obs, [action], reward, next_obs, isOver))

        # 在预热完成之后，每隔LEARN_FREQ步数就训练一次
        if (len(rpm) > MEMORY_WARMUP_SIZE) and (step % LEARN_FREQ == 0):
            (batch_obs, batch_action, batch_reward, batch_next_obs, batch_isOver) = rpm.sample(BATCH_SIZE)
            train_loss = agent.learn(batch_obs, batch_action, batch_reward, batch_next_obs, batch_isOver)

        total_reward += reward
        obs = next_obs
        # 结束游戏
        if isOver:
            break
    return total_reward


# 评估模型
def evaluate(agent, env):
    obs = env.reset()
    episode_reward = 0
    isOver = False
    while not isOver:
        obs = preprocess(obs)
        action = agent.predict(obs)
        obs, reward, isOver, info = env.step(action)
        episode_reward += reward
    return episode_reward


def main():
    # 初始化游戏
    env = flappyBird.GameState()

    # 图像输入形状和动作维度
    obs_dim = RESIZE_SHAPE
    action_dim = env.action_dim

    # 创建存储执行游戏的内存
    rpm = ReplayMemory(MEMORY_SIZE)

    # 创建模型
    model = Model(act_dim=action_dim)
    algorithm = parl.algorithms.DQN(model, act_dim=action_dim, gamma=GAMMA, lr=LEARNING_RATE)
    agent = Agent(algorithm=algorithm,
                  obs_dim=obs_dim,
                  action_dim=action_dim,
                  e_greed=E_GREED,
                  e_greed_decrement=E_GREED_DECREMENT)

    # 加载预训练模型
    if os.path.exists(SAVE_MODEL_PATH):
        agent.restore(SAVE_MODEL_PATH)

    # 预热
    print("开始预热...")
    while len(rpm) < MEMORY_WARMUP_SIZE:
        run_train(agent, env, rpm)

    # 开始训练
    print("开始正式训练...")
    episode = 0
    while episode < MAX_EPISODE:
        # 训练
        for i in range(50):
            train_reward = run_train(agent, env, rpm)
            episode += 1
            logger.info('Episode: {}, Reward: {:.2f}, e_greed: {:.2f}'.format(episode, train_reward, agent.e_greed))

        # 评估
        eval_reward = evaluate(agent, env)
        logger.info('Episode: {}, Evaluate reward:{:.2f}'.format(episode, eval_reward))

        # 保存模型
        if not os.path.exists(os.path.dirname(SAVE_MODEL_PATH)):
            os.makedirs(os.path.dirname(SAVE_MODEL_PATH))
        agent.save(SAVE_MODEL_PATH)


if __name__ == '__main__':
    main()
