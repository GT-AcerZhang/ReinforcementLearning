import numpy as np
import paddle.fluid as fluid
import parl
from parl import layers


class Agent(parl.Agent):
    def __init__(self,
                 algorithm,
                 obs_dim,
                 act_dim,
                 e_greed=0.1,
                 e_greed_decrement=0):
        assert isinstance(obs_dim, int)
        assert isinstance(act_dim, int)
        # 预测图像的shape
        self.obs_dim = obs_dim
        # 动作组合的数量
        self.act_dim = act_dim
        super(Agent, self).__init__(algorithm)

        self.global_step = 0
        self.update_target_steps = 200

        # 探索衰减参数
        self.e_greed = e_greed
        self.e_greed_decrement = e_greed_decrement

    # 获取PaddlePaddle程序
    def build_program(self):
        self.pred_program = fluid.Program()
        self.learn_program = fluid.Program()

        # 获取预测程序
        with fluid.program_guard(self.pred_program):
            obs = layers.data(name='obs', shape=[self.obs_dim], dtype='float32')
            self.value = self.alg.predict(obs)

        # 获取训练程序
        with fluid.program_guard(self.learn_program):
            obs = layers.data(name='obs', shape=[self.obs_dim], dtype='float32')
            action = layers.data(name='act', shape=[1], dtype='int32')
            reward = layers.data(name='reward', shape=[], dtype='float32')
            next_obs = layers.data(name='next_obs', shape=[self.obs_dim], dtype='float32')
            isOver = layers.data(name='isOver', shape=[], dtype='bool')
            self.cost = self.alg.learn(obs, action, reward, next_obs, isOver)

    # 获取动作
    def sample(self, obs):
        sample = np.random.rand()
        if sample < self.e_greed:
            # 随机生成动作
            act = np.random.randint(self.act_dim)
        else:
            # 预测动作
            act = self.predict(obs)
        self.e_greed = max(0.01, self.e_greed - self.e_greed_decrement)
        return act

    # 预测动作
    def predict(self, obs):
        obs = np.expand_dims(obs, axis=0)
        pred_Q = self.fluid_executor.run(program=self.pred_program,
                                         feed={'obs': obs.astype('float32')},
                                         fetch_list=[self.value])
        pred_Q = np.squeeze(pred_Q)
        action = np.argmax(pred_Q)
        return action

    # 训练模型，在固定训练次数将参数更新到目标模型
    def learn(self, obs, act, reward, next_obs, isOver):
        if self.global_step % self.update_target_steps == 0:
            # 更新目标模型参数
            self.alg.sync_target()
        self.global_step += 1

        feed = {
            'obs': obs.astype('float32'),
            'act': act.astype('int32'),
            'reward': reward,
            'next_obs': next_obs.astype('float32'),
            'isOver': isOver,
        }
        cost = self.fluid_executor.run(self.learn_program, feed=feed, fetch_list=[self.cost])[0]
        return cost
