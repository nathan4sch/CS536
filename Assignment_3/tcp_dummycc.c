#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/types.h>
#include <net/tcp.h>

/*
 * dummycc: intentionally simple congestion control for assignment testing.
 * Behavior:
 * - Slow start while cwnd < ssthresh.
 * - In congestion avoidance, grow cwnd by 1 packet every 4 ACKed packets.
 * - On loss, cut cwnd by 25% (less aggressive than Reno's 50%).
 */

#define DUMMYCC_ACKS_PER_INC 4U
#define DUMMYCC_REDUCTION_NUM 3U
#define DUMMYCC_REDUCTION_DEN 4U

static u32 tcp_dummycc_ssthresh(struct sock *sk)
{
	const struct tcp_sock *tp = tcp_sk(sk);
	u32 reduced = (tp->snd_cwnd * DUMMYCC_REDUCTION_NUM) / DUMMYCC_REDUCTION_DEN;

	return max(reduced, 2U);
}

static void tcp_dummycc_cong_avoid(struct sock *sk, u32 ack, u32 acked)
{
	struct tcp_sock *tp = tcp_sk(sk);

	if (!acked)
		return;

	if (tcp_in_slow_start(tp)) {
		acked = tcp_slow_start(tp, acked);
		if (!acked)
			return;
	}

	/* Deliberately conservative linear increase after slow start. */
	tp->snd_cwnd_cnt += acked;
	while (tp->snd_cwnd_cnt >= DUMMYCC_ACKS_PER_INC) {
		tp->snd_cwnd_cnt -= DUMMYCC_ACKS_PER_INC;
		tp->snd_cwnd++;
	}
}

static u32 tcp_dummycc_undo_cwnd(struct sock *sk)
{
	return tcp_sk(sk)->snd_cwnd;
}

static struct tcp_congestion_ops tcp_dummycc __read_mostly = {
	.flags = TCP_CONG_NON_RESTRICTED,
	.name = "dummycc",
	.owner = THIS_MODULE,
	.ssthresh = tcp_dummycc_ssthresh,
	.cong_avoid = tcp_dummycc_cong_avoid,
	.undo_cwnd = tcp_dummycc_undo_cwnd,
};

static int __init dummycc_register(void)
{
	pr_info("dummycc: registering congestion control\n");
	return tcp_register_congestion_control(&tcp_dummycc);
}

static void __exit dummycc_unregister(void)
{
	pr_info("dummycc: unregistering congestion control\n");
	tcp_unregister_congestion_control(&tcp_dummycc);
}

module_init(dummycc_register);
module_exit(dummycc_unregister);

MODULE_AUTHOR("CS536");
MODULE_DESCRIPTION("Dummy TCP congestion control for Assignment 3 testing");
MODULE_LICENSE("GPL");
