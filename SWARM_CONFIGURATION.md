# Swarm Orchestrator Configuration

The Swarm Orchestrator performance can be tuned via environment variables to balance investigation quality with speed and cost.

## 🎛️ **Configuration Parameters**

### Environment Variables

| Variable | Default | Description | Impact |
|----------|---------|-------------|---------|
| `SWARM_MAX_HANDOFFS` | `5` | Maximum agent handoffs per investigation | Higher = more specialist coordination, longer time |
| `SWARM_MAX_ITERATIONS` | `3` | Maximum investigation iterations | Higher = deeper analysis, more cost |
| `SWARM_EXECUTION_TIMEOUT` | `90.0` | Total investigation timeout (seconds) | Higher = more thorough analysis |
| `SWARM_NODE_TIMEOUT` | `30.0` | Per-agent timeout (seconds) | Higher = more time for tool execution |

## 📊 **Performance Profiles**

### 🚀 **Fast Mode** (Quick investigations)
```bash
export SWARM_MAX_HANDOFFS=3
export SWARM_MAX_ITERATIONS=2
export SWARM_EXECUTION_TIMEOUT=60.0
export SWARM_NODE_TIMEOUT=20.0
```
- **Time**: ~15-30 seconds
- **Cost**: ~$0.01-0.02
- **Quality**: Basic analysis
- **Use case**: Simple issues, cost-sensitive environments

### ⚖️ **Balanced Mode** (Default - Production ready)
```bash
export SWARM_MAX_HANDOFFS=5
export SWARM_MAX_ITERATIONS=3
export SWARM_EXECUTION_TIMEOUT=90.0
export SWARM_NODE_TIMEOUT=30.0
```
- **Time**: ~20-45 seconds
- **Cost**: ~$0.02-0.04
- **Quality**: Good analysis with root cause
- **Use case**: Most production investigations

### 🔍 **Thorough Mode** (Deep investigations)
```bash
export SWARM_MAX_HANDOFFS=8
export SWARM_MAX_ITERATIONS=5
export SWARM_EXECUTION_TIMEOUT=180.0
export SWARM_NODE_TIMEOUT=60.0
```
- **Time**: ~60-120 seconds
- **Cost**: ~$0.04-0.08
- **Quality**: Comprehensive analysis
- **Use case**: Complex issues, critical incidents

### ⚡ **Emergency Mode** (Fail-fast)
```bash
export SWARM_MAX_HANDOFFS=2
export SWARM_MAX_ITERATIONS=1
export SWARM_EXECUTION_TIMEOUT=30.0
export SWARM_NODE_TIMEOUT=10.0
```
- **Time**: ~10-20 seconds
- **Cost**: ~$0.005-0.01
- **Quality**: Minimal analysis
- **Use case**: System overload, emergency fallback

## 🐳 **Docker Configuration**

### Via docker-compose.yml
```yaml
services:
  promptrca-server:
    environment:
      # Balanced mode (default)
      - SWARM_MAX_HANDOFFS=5
      - SWARM_MAX_ITERATIONS=3
      - SWARM_EXECUTION_TIMEOUT=90.0
      - SWARM_NODE_TIMEOUT=30.0
```

### Via .env file
```bash
# Swarm Performance Configuration
SWARM_MAX_HANDOFFS=5
SWARM_MAX_ITERATIONS=3
SWARM_EXECUTION_TIMEOUT=90.0
SWARM_NODE_TIMEOUT=30.0
```

### Via command line
```bash
docker-compose up -d \
  -e SWARM_MAX_HANDOFFS=8 \
  -e SWARM_MAX_ITERATIONS=5 \
  -e SWARM_EXECUTION_TIMEOUT=180.0 \
  -e SWARM_NODE_TIMEOUT=60.0
```

## 📈 **Tuning Guidelines**

### When to Increase Parameters:
- **Complex multi-service issues** → Increase handoffs and iterations
- **Critical incidents** → Increase timeouts for thorough analysis
- **Cost is not a concern** → Use thorough mode
- **Investigation keeps timing out** → Increase execution timeout

### When to Decrease Parameters:
- **Simple single-service issues** → Use fast mode
- **High investigation volume** → Reduce for cost control
- **Performance is critical** → Use emergency mode
- **Budget constraints** → Lower iterations and handoffs

## 🎯 **Monitoring & Optimization**

### Key Metrics to Track:
- **Investigation completion rate** (should be >95%)
- **Average investigation time** (target: <60s)
- **Cost per investigation** (target: <$0.05)
- **Root cause confidence** (target: >0.70)

### Optimization Strategy:
1. **Start with balanced mode** (default settings)
2. **Monitor performance** for 1 week
3. **Adjust based on results**:
   - If timing out frequently → Increase timeouts
   - If too expensive → Reduce handoffs/iterations
   - If quality is poor → Increase parameters
   - If too slow → Use fast mode

## 🚨 **Troubleshooting**

### Common Issues:

| Problem | Likely Cause | Solution |
|---------|--------------|----------|
| Investigations timeout | Timeout too low | Increase `SWARM_EXECUTION_TIMEOUT` |
| Poor analysis quality | Too few handoffs | Increase `SWARM_MAX_HANDOFFS` |
| High costs | Too many iterations | Decrease `SWARM_MAX_ITERATIONS` |
| Slow investigations | High timeouts | Use fast mode settings |
| Tool failures | Node timeout too low | Increase `SWARM_NODE_TIMEOUT` |

### Emergency Fallback:
If swarm becomes unstable, switch to Direct orchestrator:
```bash
export PROMPTRCA_ORCHESTRATOR=direct
```

## 🔄 **Dynamic Configuration**

The swarm reads environment variables on each investigation, so you can:
- **Change settings without restart** (for containerized deployments)
- **A/B test different configurations**
- **Adjust based on system load**
- **Use different settings per environment**

## 📝 **Best Practices**

1. **Start conservative** with balanced mode
2. **Monitor and adjust** based on actual performance
3. **Use fast mode** for high-volume environments
4. **Use thorough mode** for critical incidents only
5. **Set alerts** on timeout rates and costs
6. **Document** your configuration choices
7. **Test changes** in staging first

This configuration system allows you to optimize the Swarm for your specific needs while maintaining the benefits of autonomous multi-agent investigation.